# FedSeq

FedSeq and FedSeq* implement federated top-`k` search for sequence data. This project contains the C++ benchmarks, fixed datasets and provider assignments, experiment scripts, and archived results for the synthetic DNA, synthetic Symbol, and Rfam experiments.

## How to use

### 1. Assemble the project and install dependencies

Extract all three archives into the same directory to assemble one `fedseq_revised/` project. From the directory containing the archives, run:

```bash
for part in 1 2 3; do
    unzip "FedSeq_code_part${part}(1).zip" -d FedSeq
done
cd FedSeq/fedseq_revised
```

Place this README in the `fedseq_revised/` directory. Run the commands below from that directory.

The benchmarks use Linux, a C++17 compiler with support for `unsigned __int128`, GNU Make, and the OpenSSL development library. The experiment scripts use Python 3.9 or newer and Linux CPU-affinity tools. Result analysis and plotting also require NumPy and Matplotlib. On Debian or Ubuntu:

```bash
sudo apt install build-essential libssl-dev openssl python3 python3-venv unzip util-linux
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install numpy matplotlib
```

Keep one freshly extracted copy if you plan to verify the archived results. Use a separate working copy for local builds and experiment runs. The archived Rfam audit checks the original benchmark binaries against the recorded SHA-256 hashes.

### 2. Check the project paths

| Path | Contents |
| --- | --- |
| `benchmark/` | C++ search benchmark, Makefile, and correctness tests |
| `datasets/` and `partitions/` | Synthetic DNA and Symbol sequences and fixed provider assignments |
| `supplement_datasets/` | Inputs for the family-concentration and edit-generator experiments |
| `real_data/minimal_processing/Rfam_raw/` | The fixed Rfam records, query sequences, and sample metadata |
| `real_data/raw_main/` | Rfam runner, experiment protocol, archived outputs, and summaries |
| `system/` | Local TCP and AES-128-GCM benchmarks |
| `figures/` and `paper/` | Archived figures and the manuscript snapshot shipped with the code |

The suite scripts locate inputs relative to the project directory. Use `--out-dir` to choose a location for new results. With the C++ benchmark, you can select alternate inputs with `--data`, `--queries`, and `--assignment`. Supply one sequence per line in the record and query files, and one zero-based provider ID per record in the assignment file. The assignment file follows the record order, and each ID must be smaller than `--m`.

### 3. Prepare the datasets

The archives contain the inputs for the experiments. Verify the two bundled synthetic datasets with:

```bash
python3 validate_datasets.py
```

To regenerate the original synthetic inputs in a separate directory:

```bash
python3 generate_datasets.py --out-dir local_runs/generated \
    --records 8000 --queries 52 --seed 20261010
```

The benchmark suites use 50 queries and three repetitions per configuration by default. If you regenerate provider assignments with `python3 prepare_partitions.py`, the script reads the metadata under `datasets/` and writes into `partitions/` in the working copy.

The Rfam experiments use the bundled sample of 12,391 records from families RF00001 and RF00006, plus 50 held-out query records from RF00001. The bundled sample is sufficient to rerun the experiments. See [the Rfam protocol notes](real_data/raw_main/README_CN.md) for the sampling and partitioning details.

### 4. Build and run

Build the benchmarks from source and run the checks:

```bash
make -B -C benchmark test privacy_test
make -B -C system/benchmark all test
```

#### Quick check and main synthetic suite

```bash
python3 run_suite.py --sections default --queries 1 --repeats 1 \
    --workers 1 --out-dir local_runs/smoke

python3 run_suite.py --queries 50 --repeats 3 \
    --workers 1 --out-dir local_runs/synthetic
```

The full synthetic suite compares Baseline, DANN, FedSeq, DANN*, and FedSeq* under independent and identically distributed (IID) and non-IID provider assignments. DANN* uses the experiment's common calibrated privacy budget. The suite varies one parameter at a time around `k=128`, `m=8`, `epsilon=1`, and `lambda=0.05`, then runs the ablation study. Use `--sections` with a comma-separated selection of `default,k,m,epsilon,ablation` to run specific parts.

#### Supplementary experiments

```bash
python3 run_supplement.py --queries 50 --repeats 3 \
    --workers 1 --out-dir local_runs/supplement

python3 run_negative_local.py --workers 1 --out-dir local_runs/unstructured
```

The first script runs family-concentration and alternate sequence-generation experiments and prepares inputs under `supplement_datasets/` in the working copy. The second runs a control with unstructured DNA sequences.

#### Rfam suite

```bash
mkdir -p local_runs
python3 real_data/raw_main/run.py --out-dir local_runs/rfam
```

The full Rfam launcher pins eight native workers to logical CPUs 1–8 and the replay auditor to CPU 0. Check that the process can use CPUs 0–8 before launching. On machines with fewer available CPUs, use the individual commands in `real_data/raw_main/case_index.json` and replace the archived input, binary, and output paths with local paths. The full suite runs the native comparisons, ablations, concentration experiments, and two local transport configurations.

The launcher also calls `tools/audit_quotas`. If the bundled auditor does not run on your machine, rebuild it in the working copy:

```bash
g++ -std=c++17 -O3 -Wno-unused-function tools/audit_quotas.cpp \
    benchmark/edit.cpp benchmark/filter.cpp benchmark/hash.cpp benchmark/partition.cpp \
    -lcrypto -o tools/audit_quotas
```

#### Local encrypted transport

On Linux systems with `/sys/fs/cgroup/cpu.max` available, run the matched synthetic transport suite with:

```bash
python3 system/run_system_suite.py --section matched --queries 50 --repeats 3 \
    --out-dir results/local_matched
```

This runner resolves relative output paths under `system/`. To run one configuration directly, including on Linux systems without that cgroup file:

```bash
mkdir -p local_runs
./system/benchmark/system_benchmark \
    --data system/data/dna_cluster_order/records.txt \
    --queries system/data/dna_cluster_order/queries.txt \
    --assignment system/partitions/dna_cluster_order_IID_m8.txt \
    --kind dna --backend scan --m 8 --k 128 --epsilon 1 --lambda 0.05 \
    --num-queries 1 --repeats 1 \
    --algorithms baseline,dann,fedseq,dann_star,fedseq_star \
    --privacy calibrated --noise-rng private --encryption aes128gcm \
    --transport-rtt-ms 64 --transport-mbps 100 --out local_runs/transport.csv
```

The encrypted transport benchmark uses TCP loopback with AES-128-GCM and simulates a 64 ms round-trip time and 100 Mbps bandwidth. Native suite timings report CPU time across the broker and simulated providers. Transport results also record elapsed wall time.

For `run_suite.py` and `run_supplement.py`, use `--resume` with the original parameters and output directory after interruption. Increase `--workers` only when enough physical cores are available for independent configurations. Private noise is sampled again on each run, so noisy mismatch counts can vary.

## Inspect the archived results

| Experiment | Archived results |
| --- | --- |
| Synthetic parameter sweeps and ablations | `results_calibrated/` |
| Family-concentration and edit-generator experiments | `supplement_verified/` |
| Unstructured DNA control | `unstructured/` |
| Rfam main experiments | `real_data/raw_main/cases/` and `real_data/raw_main/statistics.json` |
| Synthetic encrypted transport | `system/results/calibrated_matched/` |

The archived `case_index.json` files record per-configuration commands where available. Result CSVs contain timing and accuracy measurements. Companion files record per-provider timings and, where collected, request traces and replay information.

From a preserved extraction with the original binaries, use `python3 real_data/raw_main/analyze.py` to check the archived Rfam results and regenerate their summaries. The synthetic summary and replay scripts, `analyze_revision.py` and `audit_results.py`, use the bundled result directories and write summary, figure, or audit files into the project. Run them in a copy when keeping the archived files intact.
