"""Run three real SuperNodes on loopback; synthetic records never leave their ClientApp."""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wait_port(port, processes):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("Flower process exited; inspect runtime/spike logs")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.25)
    raise TimeoutError(f"Flower port {port} did not become ready")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for variable in ["OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"]:
        os.environ[variable] = "1"
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--tls", action="store_true")
    parser.add_argument("--adapter-configs", nargs=3, type=Path)
    args = parser.parse_args()
    if args.dataset and args.adapter_configs:
        parser.error("Choose tabular data or adapter configs")
    bundle = None
    if args.dataset:
        from medflock.node_data import prepare

        bundle = ROOT / "runtime/node-bundles"
        prepare(args.dataset.read_bytes(), bundle)

    if args.adapter_configs:
        import json

        import numpy as np

        from medflock.adapter_federation import arrays_from_adapter, load_runner

        bundle = ROOT / "runtime/adapter-spike-bundle"
        bundle.mkdir(exist_ok=True)
        _, model, _, digest, layout = load_runner(args.adapter_configs[0])
        np.savez(
            bundle / "initial-adapter.npz",
            **{f"tensor-{i:04d}": v for i, v in enumerate(arrays_from_adapter(model))},
        )
        (bundle / "server.json").write_text(
            json.dumps({"family": "causal-lora", "digest": digest, "layout": layout}),
            encoding="utf-8",
        )

    runtime = ROOT / ("runtime/spike-tls" if args.tls else "runtime/spike")
    runtime.mkdir(parents=True, exist_ok=True)
    home = runtime / "flower"
    home.mkdir(exist_ok=True)
    certificates = None
    if args.tls:
        from medflock.pki import loopback_pki

        certificates = loopback_pki(runtime / ("certs-" + uuid.uuid4().hex))
        (home / "config.toml").write_text(
            '[superlink.local-deployment]\naddress = "127.0.0.1:8000"\n'
            f'root-certificates = "{(certificates / "ca.pem").as_posix()}"\n'
        )
    else:
        shutil.copyfile(ROOT / "flwr.toml", home / "config.toml")
    env = os.environ.copy()
    env.update(FLWR_HOME=str(home), FLWR_TELEMETRY_ENABLED="0", PYTHONIOENCODING="utf-8")
    scripts = Path(sys.executable).parent
    env["PATH"] = str(scripts) + os.pathsep + env.get("PATH", "")
    processes, logs = [], []
    command = str(scripts / ("flwr.exe" if os.name == "nt" else "flwr"))
    server_security = ["--insecure"]
    if certificates:
        server_security = [
            "--ssl-certfile",
            str(certificates / "server.pem"),
            "--ssl-keyfile",
            str(certificates / "server.key"),
            "--ssl-ca-certfile",
            str(certificates / "ca.pem"),
            "--enable-supernode-auth",
        ]

    def start(name, args):
        log = (runtime / f"{name}.log").open("w", encoding="utf-8")
        logs.append(log)
        executable = str(scripts / (args[0] + (".exe" if os.name == "nt" else "")))
        processes.append(
            subprocess.Popen(
                [executable, *args[1:]],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        )

    try:
        for port in [8000, 9092, 9094, 9095, 9096]:
            with socket.socket() as check:
                if check.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError(f"Port {port} is already occupied; no services were changed")
        start(
            "superlink",
            [
                "flower-superlink",
                *server_security,
                "--host",
                "127.0.0.1",
                "--fleet-api-address",
                "127.0.0.1:9092",
                "--disable-runtime-dependency-installation",
            ],
        )
        wait_port(8000, processes)
        for index in range(3):
            node_security = ["--insecure"]
            if certificates:
                subprocess.run(
                    [
                        command,
                        "supernode",
                        "register",
                        str(certificates / f"node-{index}" / "node.pub"),
                        "local-deployment",
                        "--name",
                        f"test-node-{index}",
                    ],
                    cwd=ROOT,
                    env=env,
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                node_security = [
                    "--root-certificates",
                    str(certificates / "ca.pem"),
                    "--auth-supernode-private-key",
                    str(certificates / f"node-{index}" / "node.key"),
                ]
            start(
                f"node-{index}",
                [
                    "flower-supernode",
                    *node_security,
                    "--superlink",
                    "127.0.0.1:9092",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(9094 + index),
                    "--node-config",
                    f"partition-id={index}"
                    + (
                        f' adapter-config="{args.adapter_configs[index].resolve().as_posix()}"'
                        if args.adapter_configs
                        else (
                            f' data-dir="{(bundle / f"node-{index}").as_posix()}"' if bundle else ""
                        )
                    ),
                ],
            )
            wait_port(9094 + index, processes)
        command = str(scripts / ("flwr.exe" if os.name == "nt" else "flwr"))
        run_args = [command, "run", ".", "local-deployment", "--stream"]
        if bundle:
            run_args += ["--run-config", f'server-manifest="{(bundle / "server.json").as_posix()}"']
        completed = subprocess.run(
            run_args,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
        )
        output = completed.stdout + completed.stderr
        (runtime / "run.log").write_text(output, encoding="utf-8")
        print(output)
        if (
            completed.returncode
            or ("MEDFLOCK_ADAPTER_OK" if args.adapter_configs else "MEDFLOCK_SPIKE_OK")
            not in output
        ):
            raise RuntimeError("Transport spike failed; inspect runtime/spike logs")
    finally:
        for process in reversed(processes):
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
