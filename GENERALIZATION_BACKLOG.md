## CLI

- Remove default target concept "poutine"
- Make target_concept optional or rubric-specific
- Move SAE metadata into steering adapter
- Generalize report objectives
- Generalize compare dimensions

- Users might want to use other providers instead of anthropic's

## Prompt

> **Perform a Framework Generalization Audit.**
>
> Assume Lodestar will be used by AI researchers studying problems completely unrelated to steering.
>
> Review:
>
> * CLI
> * configuration
> * defaults
> * terminology
> * public APIs
> * reports
> * objectives
> * adapters
> * provenance
>
> Search for assumptions inherited from the original steering research.
>
> For every assumption:
>
> * explain why it exists,
> * determine whether it belongs in the core framework,
> * or whether it should move into a steering-specific adapter, plugin, rubric pack, or experiment type.
>
> The goal is not to remove steering support.
>
> The goal is to make steering one first-class application of Lodestar rather than the defining assumption of Lodestar itself.
