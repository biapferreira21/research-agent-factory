from app.schemas.capability import CapabilitySpec, KnowledgeSourceSpec, PermissionSpec


def test_capability_spec_defaults():
    spec = CapabilitySpec(
        agent_name="test_agent",
    )

    assert spec.agent_name == "test_agent"
    assert spec.capabilities == []
    assert spec.knowledge_sources == []
    assert spec.permissions == []
    assert spec.constraints == []

def test_capability_spec_with_knowledge_and_permissions():
    spec = CapabilitySpec(
        agent_name="document_agent",
        knowledge_sources=[
            KnowledgeSourceSpec(
                name="local_documents",
                description="Documents available to the agent",
                source_type="files",
            )
        ],
        permissions=[
            PermissionSpec(
                name="read_files",
                description="May read files from its workspace",
            )
        ],
    )

    assert len(spec.knowledge_sources) == 1
    assert spec.knowledge_sources[0].source_type == "files"

    assert len(spec.permissions) == 1
    assert spec.permissions[0].name == "read_files"


