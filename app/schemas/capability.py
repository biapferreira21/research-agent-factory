from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.agent import  MemorySpec, RuntimeSpec


class KnowledgeSourceSpec(BaseModel):
    name: str
    description: str
    source_type: Literal[
        "files",
         "web", 
         "database", 
         "api", 
         "vector_store"]
    required: bool = True

class PermissionSpec(BaseModel):
    name: str
    description: str
    required: bool = True


class RequiredCapabilitySpec(BaseModel):
    name: str
    description: str
    required: bool = True
    source: Literal["local", "mcp"] = "local"



class CapabilitySpec(BaseModel):
    spec_version: str = "1.0"
    agent_name: str 
    capabilities: list[RequiredCapabilitySpec] = Field(default_factory=list)
    memory: MemorySpec = Field(default_factory=MemorySpec)
    runtime: RuntimeSpec = Field(default_factory=RuntimeSpec)
    knowledge_sources: list[KnowledgeSourceSpec] = Field(default_factory=list)
    permissions: list[PermissionSpec] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)

