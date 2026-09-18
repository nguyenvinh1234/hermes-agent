import time

from app.config import ClientIdentity
from app.policy import build_write_metadata, is_visible
from app.schemas import MemoryAddRequest, MemoryClass

HERMES = ClientIdentity(client_id="hermes", agent_id="hermes", app_id="ngocviet-ai-business-os", rate_limit_per_minute=60)
OPENCLAW = ClientIdentity(client_id="openclaw", agent_id="openclaw", app_id="ngocviet-ai-business-os", rate_limit_per_minute=60)


class DummySettings:
    temporary_default_ttl_seconds = 604800


def _req(**overrides):
    base = dict(user_id="ngocviet-owner", content="fact", memory_class=MemoryClass.AGENT_PRIVATE)
    base.update(overrides)
    return MemoryAddRequest(**base)


def test_write_metadata_always_uses_identity_agent_id_never_client_input():
    metadata = build_write_metadata(HERMES, _req(), DummySettings())
    assert metadata["agent_id"] == "hermes"
    assert metadata["app_id"] == "ngocviet-ai-business-os"
    assert metadata["created_by"] == "hermes"


def test_agent_private_not_visible_to_other_agent():
    metadata = build_write_metadata(HERMES, _req(memory_class=MemoryClass.AGENT_PRIVATE), DummySettings())
    assert is_visible(
        HERMES, metadata, requested_classes=[MemoryClass.AGENT_PRIVATE], requested_project_id=None
    )
    assert not is_visible(
        OPENCLAW, metadata, requested_classes=[MemoryClass.AGENT_PRIVATE], requested_project_id=None
    )


def test_shared_visible_to_any_client():
    metadata = build_write_metadata(HERMES, _req(memory_class=MemoryClass.SHARED), DummySettings())
    assert is_visible(OPENCLAW, metadata, requested_classes=[MemoryClass.SHARED], requested_project_id=None)


def test_project_isolation():
    metadata = build_write_metadata(
        HERMES, _req(memory_class=MemoryClass.PROJECT, project_id="obsidian"), DummySettings()
    )
    assert is_visible(
        HERMES, metadata, requested_classes=[MemoryClass.PROJECT], requested_project_id="obsidian"
    )
    assert not is_visible(
        HERMES, metadata, requested_classes=[MemoryClass.PROJECT], requested_project_id="mach3-turret"
    )


def test_temporary_expires():
    metadata = build_write_metadata(
        HERMES, _req(memory_class=MemoryClass.TEMPORARY, ttl_seconds=60), DummySettings()
    )
    assert is_visible(HERMES, metadata, requested_classes=[MemoryClass.TEMPORARY], requested_project_id=None)
    metadata["expires_at"] = time.time() - 1
    assert not is_visible(
        HERMES, metadata, requested_classes=[MemoryClass.TEMPORARY], requested_project_id=None
    )


def test_archived_status_never_visible():
    metadata = build_write_metadata(HERMES, _req(memory_class=MemoryClass.SHARED), DummySettings())
    metadata["status"] = "archived"
    assert not is_visible(HERMES, metadata, requested_classes=[MemoryClass.SHARED], requested_project_id=None)


def test_class_not_requested_is_excluded():
    metadata = build_write_metadata(HERMES, _req(memory_class=MemoryClass.SHARED), DummySettings())
    assert not is_visible(
        HERMES, metadata, requested_classes=[MemoryClass.AGENT_PRIVATE], requested_project_id=None
    )
