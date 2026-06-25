# Transparency Note: Amorphware (Apeiron)

## About this Transparency Note

Microsoft Transparency Notes are intended to help you understand how an AI
technology works, the choices system owners can make that influence system
performance and behavior, and the importance of thinking about the whole
system — including the technology, the people, and the environment. This note
covers **Apeiron / Amorphware**, a research framework that uses LLM-driven
agents to synthesize and iteratively refine application code through a
Computer-Use-Agent (CUA) build loop.

This is a **research preview**. It is not a supported product and is not
intended for production or high-stakes use.

## The basics

### What is Amorphware (Apeiron)?

Apeiron orchestrates large language model (LLM) agents to assemble and iterate
on *target* application code. A constrained CUA build loop drives the
construction process from configuration and bound libraries. The output is
experimental software ("amorphware").

### What can it do?

- Synthesize and iteratively refine target applications from configuration.
- Run distributed builds across isolated workers (one CUA = one port = one
  isolated virtual environment).
- Provide a monitoring GUI and tracing for build runs.

### Intended uses

- Academic and research exploration of agentic software-construction pipelines.
- Controlled experiments in sandboxed, **non-production** environments.

## Capabilities & limitations

### Key boundaries (by design)

- **No self-modification / self-improvement.** The system is scoped so that it
  cannot modify, retrain, or extend its own agent code, prompts, model weights,
  or orchestration logic. It builds *target* applications only. This boundary is
  intentional and must be preserved.
- **Not autonomous beyond the build task.** Agents operate within configured
  build/CICD functions and the explicitly bound libraries.
- **Sandbox assumption.** The system assumes isolated, non-production execution.

### Limitations

- **Correctness / reliability.** Generated code is experimental and may be
  incorrect, insecure, or non-functional. Human review is required before any
  use.
- **Hallucination.** LLM agents can produce inaccurate or fabricated output.
- **Non-determinism.** Results can vary across runs.
- **Environment sensitivity.** Behavior depends on model versions, endpoints,
  bound libraries, and configuration chosen by the operator.

## Risks and mitigations

| Risk | Description | Mitigation / boundary |
|------|-------------|------------------------|
| Malicious / unsafe code generation | The system synthesizes and executes code and could be prompted to produce harmful or insecure output. | Run only in isolated sandboxes; require human review of all artifacts; no production systems, credentials, or networks. |
| Sensitive / high-stakes domains | Not evaluated or approved for safety-critical, medical, legal, financial-decisioning, or rights-affecting use. | Such uses are out of scope and prohibited. |
| Self-directed behavior | Concern about recursive self-modification. | System scoped to prevent acting on itself; boundary must be preserved. |
| Inaccurate output | LLM hallucination / errors. | Treat all output as untrusted draft requiring validation. |
| Data exposure | Sensitive or personal data entered into the system. | Provide only non-sensitive, non-personal data; do not input regulated/confidential data. |

## Data, privacy, and security

- **Operator-provided data.** Operators choose what data and configuration the
  system processes. Provide only non-sensitive, non-personal data.
- **Credentials.** Endpoints and API keys are supplied by the operator via
  environment variables (`.env`, which is gitignored) and must never be
  committed. See `.env.example`.
- **Third-party models / services.** The system can be configured to call
  third-party model endpoints and data APIs; operators are responsible for
  complying with those providers' terms.
- **Security reporting.** See `SECURITY.md`.

## Responsible and effective use

- Use only for research in isolated, non-production environments.
- Keep a human in the loop; review all generated artifacts before use.
- Do not use in sensitive/high-stakes domains or to generate harmful code.
- Do not remove or weaken the capability limits described above.

## Learn more

- README: `README.md`
- Security policy: `SECURITY.md`
- Code of Conduct: `CODE_OF_CONDUCT.md`
- Microsoft Responsible AI: https://www.microsoft.com/ai/responsible-ai

---

*This Transparency Note is a draft and does not constitute legal advice or an
approved disclosure. Final wording is subject to Responsible AI and legal
review.*
