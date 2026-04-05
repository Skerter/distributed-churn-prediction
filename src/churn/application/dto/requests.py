from dataclasses import dataclass


@dataclass(slots=True)
class RunPipelineRequest:
    profile: str
    execute: bool = False