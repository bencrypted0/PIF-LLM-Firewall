# Red-Team Auditing with NVIDIA garak & PyRIT

This document outlines how to build and run the red-teaming container to audit the prompt injection firewall and the backend agent.

---

## 1. Prerequisites

Ensure the main chatbot application stack is running:
```bash
# Run this from the repository root
docker-compose up --build
```
This starts the backend agent (listening on `backend:8000` internally) and the proxy firewall (listening on `firewall:5000` internally).

---

## 2. Setup the Attack Tester Image

From the `red-team` directory, build the security testing Docker image:
```bash
# Run this from the red-team folder
docker build -t attack-tester .
```

---

## 3. Run the Attack Container

To allow `garak` and `pyrit` to talk to the firewall and backend containers, the `attack-tester` container **must be on the same Docker network** as the application stack.

1. Find the name of the Docker Compose network:
   ```bash
   docker network ls
   ```
   *(Usually, it is named `pim-injection-firewall_default` or `pim-injection-firewall_default`)*.

2. Start the interactive container using the `--network` option:
   ```bash
   # From the red-team folder (using PowerShell syntax for $(pwd)):
   docker run -it --rm \
     --network pim-injection-firewall_default \
     -v ${PWD}/config:/workspace/config \
     -v ${PWD}/results:/workspace/results \
     --name attack-tester \
     attack-tester
   ```
   *(If using standard bash/zsh on Linux or macOS, replace `${PWD}` with `$(pwd)`)*.

---

## 4. Run the Security Scans (Inside the Container)

Once inside the `attack-tester` container shell, you can run the following tools:

### A. Run garak (LLM Vulnerability Scanner)
To execute scans using `garak` against the REST endpoint configuration:
```bash
garak --model_type rest -G config/garak_rest.json --probes promptinject,dan,encoding,malwaregen
```

* **Targeting details (in `config/garak_rest.json`)**:
  * **Test the Firewall**: Set `"uri": "http://firewall:5000/chat"` (default) to audit the firewall's blocking capabilities.
  * **Test the Backend directly (Bypass)**: Set `"uri": "http://backend:8000/chat"` to see how vulnerable the underlying model is without the firewall.

---

### B. Run PyRIT (Python Risk Identification Tool)
A PyRIT test harness is available at `config/pyrit_test.py`. It compares the response from the firewall versus the direct backend:
```bash
python config/pyrit_test.py
```
This runs:
1. **Direct HTTP checks**: Sends safe and malicious payloads to both endpoints to verify block vs allow.
2. **PyRIT Orchestrator session**: Runs PyRIT's target and orchestrator setup to run a test prompt sequence.

---

## 5. Review Results

* **garak** reports and logs will be written to `/workspace/results` (maps back to `red-team/results/` on your host machine).
* **PyRIT** details will print directly to the console or log to the default PyRIT local databases inside `/workspace`.
