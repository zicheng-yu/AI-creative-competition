"""Published trace facts cited by the data note.

These constants are documentation anchors. The arrival generator does not read
them and does not claim to reproduce the underlying distributions.
"""

from __future__ import annotations

PUBLISHED_ANCHORS = {
    "alibaba_pai_v2020": {
        "citation": "Weng et al., MLaaS in the Wild, NSDI 2022",
        "url": "https://www.usenix.org/system/files/nsdi22-paper-weng.pdf",
        "trace_repo": "https://github.com/alibaba/clusterdata/tree/master/cluster-trace-gpu-v2020",
        "gpus": 6742,
        "period": "July–August 2020",
        "tasks": "more than 1.2 million",
        "instances": "more than 7.5 million",
        "median_instance_runtime_min": 23,
        "philly_median_instance_runtime_min_as_reported": 26,
        "tasks_pinning_gpu_type_percent": 6,
        "qualitative": [
            "weekday submissions slightly higher than weekend",
            "daytime submissions plus a midnight rush of smaller jobs",
            "instance runtime spans roughly four orders of magnitude",
        ],
    },
    "helios": {
        "citation": "Hu et al., Characterization and Prediction of Deep Learning Workloads in Large-Scale GPU Datacenters, SC 2021",
        "url": "https://arxiv.org/abs/2109.01313",
        "trace_repo": "https://github.com/S-Lab-System-Group/HeliosData",
        "clusters": 4,
        "nodes": 802,
        "gpus": 6416,
        "jobs_paper": "3.36 million",
        "jobs_repo_readme": 3362981,
        "gpu_jobs_repo_readme": 1580464,
        "period": "April–September 2020",
        "utilization_range_percent": [65, 90],
        "night_utilization_drop_percent": [5, 8],
        "unsuccessful_gpu_jobs_percent": 37.6,
    },
    "philly": {
        "citation": "Jeon et al., Analysis of Large-Scale Multi-Tenant GPU Clusters for DNN Training Workloads, USENIX ATC 2019",
        "trace_repo": "https://github.com/msr-fiddle/philly-traces",
        "note": "Median runtime is quoted only as reported by Weng et al.; this package does not refit Philly.",
    },
}
