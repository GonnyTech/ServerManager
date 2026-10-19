"""
Docker Manager for Server Guardian.
Handles container inspection, semantic version analysis, upgrade policies, and safe recreation.
"""

import re
import urllib.request
import json
from typing import List, Dict, Any, Optional, Tuple
from packaging.version import parse as parse_version, Version

import docker
from docker.errors import DockerException, APIError

from server_guardian.config import GuardianConfig
from server_guardian.mailer import Mailer

# Regex to detect SemVer strings like 1.2.3 or v2.4.1
SEMVER_REGEX = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?$")


class DockerManager:
    def __init__(self, config: Optional[GuardianConfig] = None):
        self.config = config or GuardianConfig.load()
        self.mailer = Mailer(self.config)
        self._client: Optional[docker.DockerClient] = None
        # In-memory tracking of pending updates (container_id -> info dict)
        self.pending_updates: Dict[str, Dict[str, Any]] = {}

    def get_client(self) -> Optional[docker.DockerClient]:
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client.ping()
            except Exception:
                self._client = None
        return self._client

    def is_docker_available(self) -> bool:
        client = self.get_client()
        return client is not None

    def list_containers(self) -> List[Dict[str, Any]]:
        """List all containers with status, health, image, and pending update flag."""
        client = self.get_client()
        if not client:
            return []

        result = []
        try:
            containers = client.containers.list(all=True)
            for c in containers:
                attrs = c.attrs
                status = c.status
                health = attrs.get("State", {}).get("Health", {}).get("Status", "none")

                # Image and Tag
                image_tags = c.image.tags if c.image.tags else []
                primary_image = image_tags[0] if image_tags else c.image.short_id

                pending_info = self.pending_updates.get(c.id)

                result.append({
                    "id": c.short_id,
                    "full_id": c.id,
                    "name": c.name,
                    "status": status,
                    "health": health,
                    "image": primary_image,
                    "image_id": c.image.short_id,
                    "created": attrs.get("Created", "")[:19],
                    "pending_update": pending_info is not None,
                    "pending_details": pending_info,
                })
        except Exception:
            pass

        return result

    def get_pending_updates(self) -> List[Dict[str, Any]]:
        """Return list of containers waiting for manual confirmation."""
        return list(self.pending_updates.values())

    @staticmethod
    def parse_semver_tag(tag: str) -> Optional[Tuple[int, int, int]]:
        """Extract (major, minor, patch) from a tag like '1.2.3' or 'v1.2.3'."""
        match = SEMVER_REGEX.match(tag)
        if not match:
            return None
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3)) if match.group(3) else 0
        return (major, minor, patch)

    def check_remote_tags(self, image_repo: str) -> List[str]:
        """
        Query Docker Hub registry tags for an image repository.
        Supports official library (e.g., 'nginx') and namespaced (e.g., 'library/ubuntu').
        """
        repo = image_repo
        if "/" not in repo:
            repo = f"library/{repo}"

        url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags?page_size=50"
        req = urllib.request.Request(url, headers={"User-Agent": "ServerGuardian/1.0"})
        tags = []
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    for result in data.get("results", []):
                        name = result.get("name")
                        if name:
                            tags.append(name)
        except Exception:
            pass
        return tags

    def check_container_for_update(self, container_obj) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Inspect container image and determine if an update is available.
        Returns:
            (policy_action, current_version, new_version_or_digest)
            policy_action: 'none', 'auto_upgrade', 'incremental_pending', 'latest_pending'
        """
        client = self.get_client()
        if not client:
            return "none", None, None

        image_tags = container_obj.image.tags
        if not image_tags:
            return "none", None, None

        full_image_name = image_tags[0]
        if ":" in full_image_name:
            repo, current_tag = full_image_name.rsplit(":", 1)
        else:
            repo, current_tag = full_image_name, "latest"

        # Case 1: Tag is ':latest'
        if current_tag == "latest":
            try:
                # Check remote registry digest vs local image digest
                remote_img = client.images.get_registry_data(f"{repo}:latest")
                current_id = container_obj.image.id
                remote_id = remote_img.id if hasattr(remote_img, "id") else None

                if remote_id and remote_id != current_id:
                    return "latest_pending", current_id[:12], remote_id[:12]
            except Exception:
                pass
            return "none", None, None

        # Case 2: Tag is SemVer
        curr_semver = self.parse_semver_tag(current_tag)
        if not curr_semver:
            return "none", None, None

        available_tags = self.check_remote_tags(repo)
        best_candidate = None
        candidate_semver = None

        for t in available_tags:
            s = self.parse_semver_tag(t)
            if s and s > curr_semver:
                if candidate_semver is None or s > candidate_semver:
                    candidate_semver = s
                    best_candidate = t

        if not best_candidate or not candidate_semver:
            return "none", None, None

        curr_major, curr_minor, curr_patch = curr_semver
        cand_major, cand_minor, cand_patch = candidate_semver

        # If Major or Minor changed -> Auto Upgrade
        if cand_major > curr_major or cand_minor > curr_minor:
            return "auto_upgrade", current_tag, best_candidate

        # If only Patch/Incremental changed -> Manual Approval Pending
        if cand_patch > curr_patch:
            return "incremental_pending", current_tag, best_candidate

        return "none", None, None

    def run_nightly_docker_checks(self) -> Dict[str, Any]:
        """
        Nightly check triggered at 02:00:
        1. Checks all active containers.
        2. Auto-updates Major/Minor versions. Sends failure mail if error occurs.
        3. Halts auto-updates for incremental/patch and :latest, queueing them and sending emails.
        """
        client = self.get_client()
        if not client:
            return {"status": "error", "message": "Docker service unavailable."}

        summary = {
            "auto_upgraded": [],
            "incremental_pending": [],
            "latest_pending": [],
            "failures": [],
        }

        try:
            containers = client.containers.list(all=False)
        except Exception as e:
            return {"status": "error", "message": str(e)}

        for c in containers:
            action, cur_ver, new_ver = self.check_container_for_update(c)

            if action == "auto_upgrade":
                success, msg = self.recreate_container_with_new_image(c.id, new_ver)
                if success:
                    summary["auto_upgraded"].append({"name": c.name, "from": cur_ver, "to": new_ver})
                else:
                    summary["failures"].append({"name": c.name, "from": cur_ver, "to": new_ver, "error": msg})
                    self.mailer.notify_docker_update_failure(c.name, str(cur_ver), str(new_ver), msg)

            elif action == "incremental_pending":
                self.pending_updates[c.id] = {
                    "container_id": c.id,
                    "container_name": c.name,
                    "current_version": cur_ver,
                    "target_version": new_ver,
                    "type": "incremental",
                    "detected_at": c.attrs.get("Created", "")[:19],
                }
                summary["incremental_pending"].append({"name": c.name, "from": cur_ver, "to": new_ver})
                self.mailer.notify_docker_incremental_pending(c.name, str(cur_ver), str(new_ver))

            elif action == "latest_pending":
                self.pending_updates[c.id] = {
                    "container_id": c.id,
                    "container_name": c.name,
                    "current_version": cur_ver,
                    "target_version": new_ver,
                    "type": "latest_digest",
                    "detected_at": c.attrs.get("Created", "")[:19],
                }
                summary["latest_pending"].append({"name": c.name, "digest": new_ver})
                self.mailer.notify_docker_latest_digest_pending(
                    c.name, c.image.tags[0] if c.image.tags else c.name, str(cur_ver), str(new_ver)
                )

        return {"status": "success", "summary": summary}

    def recreate_container_with_new_image(self, container_id: str, new_tag_or_digest: str) -> Tuple[bool, str]:
        """
        Safely recreate a container using updated image preserving all ports, envs, volumes and networks.
        """
        client = self.get_client()
        if not client:
            return False, "Docker client unavailable"

        try:
            container = client.containers.get(container_id)
        except Exception as e:
            return False, f"Container not found: {e}"

        attrs = container.attrs
        name = container.name
        config = attrs.get("Config", {})
        host_config = attrs.get("HostConfig", {})

        # Extract current image repo
        image_tags = container.image.tags
        current_full_image = image_tags[0] if image_tags else container.image.id
        if ":" in current_full_image:
            repo, _ = current_full_image.rsplit(":", 1)
        else:
            repo = current_full_image

        target_image = f"{repo}:{new_tag_or_digest}" if ":" not in new_tag_or_digest else new_tag_or_digest

        # Pull new image first
        try:
            client.images.pull(target_image)
        except Exception as e:
            return False, f"Failed to pull image {target_image}: {e}"

        # Capture configuration for recreation
        environment = config.get("Env", [])
        command = config.get("Cmd")
        entrypoint = config.get("Entrypoint")
        labels = config.get("Labels", {})

        # Port bindings: { '80/tcp': [{'HostIp': '', 'HostPort': '8080'}] } -> {'80/tcp': ('0.0.0.0', 8080)}
        raw_ports = host_config.get("PortBindings") or {}
        ports = {}
        for container_port, bindings in raw_ports.items():
            if bindings:
                host_port = bindings[0].get("HostPort")
                host_ip = bindings[0].get("HostIp", "")
                ports[container_port] = (host_ip, int(host_port)) if host_port else None

        # Binds / Mounts
        binds = host_config.get("Binds", [])

        # Restart policy
        restart_policy = host_config.get("RestartPolicy", {})

        # Network configuration
        network_mode = host_config.get("NetworkMode", "default")

        # Rename existing container to backup name
        backup_name = f"{name}_guardian_bak"
        try:
            # Check if an old backup container exists and remove it
            try:
                old_bak = client.containers.get(backup_name)
                old_bak.remove(force=True)
            except Exception:
                pass

            container.stop(timeout=15)
            container.rename(backup_name)
        except Exception as e:
            return False, f"Failed to stop and rename container before recreation: {e}"

        # Create and start new container
        try:
            new_container = client.containers.create(
                image=target_image,
                name=name,
                command=command,
                entrypoint=entrypoint,
                environment=environment,
                ports=ports,
                volumes=binds,
                restart_policy=restart_policy if restart_policy.get("Name") else None,
                network=network_mode if network_mode != "default" else None,
                labels=labels,
            )
            new_container.start()

            # Remove old backup container on success
            try:
                container.remove(force=True)
            except Exception:
                pass

            # Remove from pending queue if present
            self.pending_updates.pop(container_id, None)

            return True, f"Container '{name}' successfully updated to {target_image}"

        except Exception as e:
            # Rollback: attempt to restore backup container
            try:
                container.rename(name)
                container.start()
            except Exception:
                pass
            return False, f"Failed to start recreated container with {target_image}: {e}"

    def force_manual_update(self, container_id: str) -> Tuple[bool, str]:
        """
        Manually trigger pending container upgrade directly from TUI.
        """
        pending = self.pending_updates.get(container_id)
        if not pending:
            return False, "No pending update found for this container."

        target_version = pending.get("target_version")
        if not target_version:
            return False, "Target version not specified."

        return self.recreate_container_with_new_image(container_id, target_version)
