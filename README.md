# Apeiron

Apeiron is a research system for building **amorphware** — software that is
synthesized and iteratively refined by LLM-driven agents through a
Computer-Use-Agent (CUA) build loop.

> **Research preview / non-production.** This project is released for
> research and educational purposes. It is **not** a supported product and is
> not intended for production or high-stakes use. See
> [Intended Use & Scope](#intended-use--scope), [Capability Limits](#capability-limits),
> and [Responsible AI: Risks & Mitigations](#responsible-ai-risks--mitigations) below.

---

## Table of Contents

- [Paper](#paper)
- [Intended Use & Scope](#intended-use--scope)
- [Capability Limits](#capability-limits)
- [Responsible AI: Risks & Mitigations](#responsible-ai-risks--mitigations)
- [Out-of-Scope and Prohibited Uses](#out-of-scope-and-prohibited-uses)
- [Installation](#installation)
- [Configuration (.env)](#configuration-env)
- [How to use](#how-to-use)
- [How to extend the framework](#how-to-extend-the-framework)
- [Contributing](#contributing)
- [Security](#security)
- [Code of Conduct](#code-of-conduct)
- [Trademarks](#trademarks)
- [License](#license)

---

## Paper

Apeiron is described in our paper [**"Apeiron: A Scalable LLM-agentic Framework
for Autonomous Full-lifecycle Demand-optimized Application Synthesis"**](https://aclanthology.org/2026.findings-acl.188/),
accepted to the **Findings of the Association for Computational Linguistics:
ACL 2026**.

If you use Apeiron in your research, please cite:

```bibtex
@inproceedings{cheng-etal-2026-apeiron,
    title = "Apeiron: A Scalable {LLM}-agentic Framework for Autonomous Full-lifecycle Demand-optimized Application Synthesis",
    author = "Cheng, Junyan  and
      Srivastava, Ankit  and
      Zeng, Jessie  and
      Drinic, Milenko  and
      Stokes, Jack W.",
    editor = "Liakata, Maria  and
      Moreira, Viviane P.  and
      Zhang, Jiajun  and
      Jurgens, David",
    booktitle = "Findings of the {A}ssociation for {C}omputational {L}inguistics: {ACL} 2026",
    month = jul,
    year = "2026",
    address = "San Diego, California, United States",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2026.findings-acl.188/",
    pages = "3868--3899",
    ISBN = "979-8-89176-395-1",
    abstract = "We introduce Apeiron, a scalable and extensible framework for addressing *amorphous* user demands through autonomous, full-lifecycle application synthesis. Apeiron models the unstructured app development process as a heuristic optimization problem combining (i) a Computer-Use Agent (CUA) evaluator that simulates personas and demands, (ii) an *Activity Tracer* that grounds feedback in code-level interaction traces, and (iii) a *Locality Controller* that constrains changes during continuous integration and delivery (CI/CD). Furthermore, we introduce an innovative data generation approach using CUA-as-a-Judge to tackle data scarcity. Across 300 app scenarios, 2,400 personas, and 46,338 demands, Apeiron outperformed baselines by 10.7{\%} in CUA ratings and 27.8{\%} in user-demand task scores. The optimization process enhances task scores by 64.7{\%}, and the tracer contributes a 25.1{\%} gain. In CI/CD, Apeiron effectively restores 96.9{\%} of the pre-shift mean CUA rating in one optimization step with {\ensuremath{<}}30{\%} code changes in response to 30{\%} demand shifts. Finally, a user study ($N=18$) shows that our CUA ratings strongly correlate with human judgment (Spearman{'}s $\rho=0.685$) and that users prefer Apeiron-synthesized apps over baselines."
}
```

---

## Intended Use & Scope

Apeiron is intended **only** as a research framework that orchestrates LLM
agents to assemble and iterate on application code via a constrained
Computer-Use-Agent (CUA) build loop. Its purpose is to study agentic software
construction.

**The system is scoped so that it cannot actively work on or improve itself.**
The CUA loop builds *target applications* from configuration and library
bindings; it does not have a pathway to modify, retrain, or extend its own
agent code, model weights, or orchestration logic. This boundary is
intentional and is a condition of release — please preserve it when extending
the framework.

Appropriate uses:
- Academic / research exploration of agentic build pipelines.
- Controlled experiments in sandboxed, non-production environments.

## Capability Limits

- **No self-modification / self-improvement.** Apeiron builds external apps via
  the CUA loop; it is not designed to modify its own source, prompts, or models
  at runtime.
- **Not autonomous beyond the build task.** Agents operate within the
  configured build/CICD functions (`build`, `build_cicd`, `xbuild`) and the
  bound libraries declared in `configs`. It is not a general-purpose autonomous
  agent.
- **No guarantees of correctness or safety of generated code.** Output is
  experimental and must be reviewed by a human before any use.
- **Sandboxed execution assumed.** The system spins up many isolated venvs/ports
  per CUA worker and assumes it runs in an isolated, non-production environment.

## Responsible AI: Risks & Mitigations

Known risks and the mitigations / boundaries that apply:

- **Generation of malicious or unsafe code.** Because the system synthesizes
  and executes code, it could be prompted to produce harmful, insecure, or
  malicious output. *Mitigation:* run only in isolated sandboxes; require human
  review of all generated artifacts; do not connect to production systems,
  credentials, or networks.
- **Sensitive / high-stakes domains.** The system is **not** evaluated or
  approved for use in sensitive domains (e.g., safety-critical, medical, legal,
  financial decisioning, or any setting affecting the rights, safety, or
  livelihood of individuals). *Mitigation:* such uses are out of scope and
  prohibited (see below).
- **Self-directed behavior.** As noted above, the system is scoped to prevent
  acting on itself; this boundary mitigates self-improvement / recursive
  self-modification concerns and must be preserved.
- **Hallucination / incorrect output.** LLM agents can produce inaccurate or
  unreliable results. *Mitigation:* treat all output as untrusted draft
  material requiring validation.
- **Data handling.** Provide only non-sensitive, non-personal data to the
  system. Do not input regulated, confidential, or personal data.

For the full intended-use, evaluation, and limitation disclosures, see the
project [**Transparency Note**](TRANSPARENCY_NOTE.md).

## Out-of-Scope and Prohibited Uses

The following are explicitly out of scope and must not be attempted:
- Production deployment or any high-stakes / sensitive-domain use.
- Generating malware, exploits, or other harmful code.
- Allowing the system to operate against real users, production data, or live
  credentials/networks.
- Modifying the framework to enable self-improvement or removal of the
  capability limits described above.

---

## Installation

### Install conda

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

### Setup environment

```bash
conda create -n apeiron python=3.13 -y &&\
cd YOUR_DIR/amorphware &&\
conda activate apeiron &&\
pip install -e . &&\
pip install -r requirements.txt &&\
python -m ipykernel install --user --name "apeiron" --display-name "Python (apeiron)"
```

### Install playwright

```bash
python -m playwright install
```

Note: you may need to install additional OS dependencies — please read the
output from `playwright install` carefully. You may also need Node and possibly
Next.js installed if you wish to use reflex.

### Install Stracelit

```bash
pip install apeiron/btool/streamlit_tracer/.
```

(Assumes you are in the `amorphware` folder.)

---

## Configuration (.env)

Copy [`.env.example`](.env.example) to `.env` and fill in your own values.
**`.env` is gitignored and must never be committed.** Never commit real
secrets, keys, or personal endpoints.

```bash
cp .env.example .env
```

### Authentication

By default Apeiron authenticates to Azure OpenAI / AI Foundry with your **Entra
ID identity** rather than an API key (`AZURE_OPENAI_AUTH_MODE=interactive`, the
default):

1. It first tries an existing `az login` session (silent, no browser).
2. Otherwise it opens a browser **once** for an interactive login. The
   resulting authentication record is cached under `~/.apeiron/auth/`, so later
   runs acquire tokens silently from the OS-encrypted token cache without
   reopening the browser.
3. If no token can be acquired (e.g. a headless/CI box with no cached login)
   and `AZURE_AI_FOUNDRY_KEY` is set, it falls back to the API key.

To use the API key exclusively (e.g. headless/CI), set
`AZURE_OPENAI_AUTH_MODE=key`. Set `AZURE_OPENAI_AUTH_VERIFY=0` to defer login to
the first request instead of checking eagerly at startup. See
[`.env.example`](.env.example) for all auth-related variables.

### About CUA

This project does not ship CUA model deployments. Configure your own CUA
endpoint and key via environment variables (see `.env.example`) rather than
hardcoding them in source. The computer-use model card reads its endpoint from
the `AZURE_CUA_ENDPOINT` environment variable.

**Note (Windows):** you may need to enable **Long Path Support** (260-char
limit on older versions):
1. Open the Registry Editor (`regedit`).
2. Navigate to `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem`.
3. Set the `LongPathsEnabled` DWORD value to `1` (create it if missing).
4. A restart may be required.
Details: https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation

### Suggestions

1. Use a large SSD when running experiments — many venvs may be created. By
   default it supports up to 2000 concurrent CUA workers; to change this, edit
   the length in `find_free_port`. One CUA = one port = one venv (favours
   stability over efficiency).
2. To avoid `OSError: [Errno 24] inotify instance limit reached`:
   1. `sudo vim /etc/sysctl.conf`
   2. append `fs.inotify.max_user_watches=524288`
   3. append `fs.inotify.max_user_instances=1000000`
   4. run `sudo sysctl -p` to apply.

---

## How to use

> Run only in an isolated, non-production sandbox. See
> [Responsible AI](#responsible-ai-risks--mitigations).

1. To run a full experiment (from the `amorphware` root directory):

   ```bash
   python scripts/run_exp.py
   ```

   You may wish to change the config and `exp_name` first — in particular you
   can edit the libraries bound via the `bind_libraries` field in the config
   files under `configs`.

2. In the system class, the main entry points are `build` and `build_cicd`
   (initial build and CICD build respectively). `xbuild` launches the
   distributed build.

3. To launch the monitoring GUI:

   ```bash
   streamlit run bin/app.py
   ```

---

## How to extend the framework

1. **Add a new library:** create a file under `apeiron/library/` (follow the
   format of existing libraries), then add it to the `bind_libraries` field in
   the relevant config under `configs`.
2. **Extend the LLMs:** update `sllm/const.py`.
3. **Add a new agent:** create a file under `apeiron/agent/prompts` and register
   it in `apeiron/agent/aw.py`.
4. **Add a new framework target:** implement the `Compiler` class in
   `apeiron/btool/compilers.py` (see the existing Streamlit compiler).
5. **Extend the tracer:** see `apeiron/btool/streamlit_tracer`. The key is to
   produce the ACT and Traces defined in `apeiron/btool/ir.py`.

> When extending, do not introduce pathways that let the system modify its own
> code/models or bypass the capability limits — this is a release condition.

---

## Contributing

This project welcomes contributions and suggestions. Most contributions require
you to agree to a Contributor License Agreement (CLA) declaring that you have
the right to, and actually do, grant us the rights to use your contribution.
For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether
you need to provide a CLA and decorate the PR appropriately. Follow the
instructions provided by the bot. You will only need to do this once across all
repos using our CLA.

## Security

Please see [SECURITY.md](SECURITY.md) for how to report security issues. Do not
file security vulnerabilities as public issues.

## Code of Conduct

This project has adopted the
[Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details.

## Trademarks

This project may contain trademarks or logos for projects, products, or
services. Authorized use of Microsoft trademarks or logos is subject to and must
follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must
not cause confusion or imply Microsoft sponsorship. Any use of third-party
trademarks or logos is subject to those third parties' policies.

## License

Licensed under the [MIT License](LICENSE).
