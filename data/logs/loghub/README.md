# LogHub Datasets

This directory contains real-world production log datasets from [LogHub](https://github.com/logpai/loghub).

## Available Datasets

| Dataset | Description | Download Link |
|---------|-------------|---------------|
| **Zookeeper** | Apache Zookeeper coordination service logs | [Zenodo](https://zenodo.org/records/8196385/files/Zookeeper.tar.gz) |
| **Hadoop** | Hadoop MapReduce job execution logs | [Zenodo](https://zenodo.org/records/8196385/files/Hadoop.zip) |

## Download Instructions

These datasets are not included in the git repository due to their size (50MB+). To download:

### Zookeeper (10MB, 74K lines)

```powershell
# PowerShell
cd data/logs/loghub/zookeeper
Invoke-WebRequest -Uri "https://zenodo.org/records/8196385/files/Zookeeper.tar.gz?download=1" -OutFile "Zookeeper.tar.gz"
tar -xzf Zookeeper.tar.gz
```

```bash
# Bash
cd data/logs/loghub/zookeeper
curl -L "https://zenodo.org/records/8196385/files/Zookeeper.tar.gz?download=1" -o Zookeeper.tar.gz
tar -xzf Zookeeper.tar.gz
```

### Hadoop (48MB, 394K lines)

```powershell
# PowerShell
cd data/logs/loghub/hadoop
Invoke-WebRequest -Uri "https://zenodo.org/records/8196385/files/Hadoop.zip?download=1" -OutFile "Hadoop.zip"
Expand-Archive -Path Hadoop.zip -DestinationPath .
```

```bash
# Bash
cd data/logs/loghub/hadoop
curl -L "https://zenodo.org/records/8196385/files/Hadoop.zip?download=1" -o Hadoop.zip
unzip Hadoop.zip
```

## Log Format Examples

### Zookeeper
```
2015-07-29 17:41:41,536 - INFO  [main:QuorumPeerConfig@101] - Reading configuration from: conf/zoo.cfg
2015-07-29 17:41:41,544 - WARN  [main:QuorumPeerConfig@244] - No server failure will be tolerated.
```

### Hadoop
```
2015-10-17 15:37:56,547 INFO [main] org.apache.hadoop.mapreduce.v2.app.MRAppMaster: Created MRAppMaster
2015-10-17 15:37:58,412 INFO [main] org.apache.hadoop.mapreduce.v2.app.job.impl.JobImpl: Adding job token
```

## Citation

If you use these datasets, please cite:

```bibtex
@article{he2020loghub,
  title={Loghub: A large collection of system log datasets towards automated log analytics},
  author={He, Shilin and Zhu, Jieming and He, Pinjia and Lyu, Michael R},
  journal={arXiv preprint arXiv:2008.06448},
  year={2020}
}
```

