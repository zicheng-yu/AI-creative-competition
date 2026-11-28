"""Curator-locked FluEvidenceBench-v1: published records, two tasks, offline metrics.

Public identifiers were read from NCBI, RCSB, IEDB, and UniProt on 2026-11-28.
Capsules store titles, definition lines, or database summaries. They do not store
nucleotide sequences, construct recipes, or new biological scores.
"""
import csv
import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter_ns

from benchmarks.metrics import ndcg
from benchmarks.offline import offline_runtime
from engine.audit import _EFFECT_PROMISE
from engine.capsules import Snapshot, canonical, database_source_url, digest
from engine.dossiers import Dossier, archive_digest
from engine.llm_adapter import BaseLLMClient, Citation
from engine.models import TextModels

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "FluEvidenceBench-v1"
V1 = "fluevidence-v1"
V2 = "fluevidence-v1.1"
AT_V1 = "2026-11-28T06:00:00+08:00"
AT_V2 = "2026-11-28T09:00:00+08:00"
CITE = "此胶囊只保存已核验的公开题名或数据库原文，不把来源中的结果句当作本原型的疗效结论。"

RECORDS = (
    dict(evidence_id="EV-REF-GARTEN", source_type="PUBMED_LITERATURE", primary_ref="PMID:19465683",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="A/H1N1pdm09 reference-strain literature",
         title="Antigenic and genetic characteristics of swine-origin 2009 A(H1N1) influenza viruses circulating in humans.",
         published_on="2009-07-10", topics=("reference-strain", "h1n1pdm09"),
         review_status="accepted",
         archive_note="NCBI esummary pubdate 2009 Jul 10. Title citation only."),
    dict(evidence_id="EV-REF-SMITH", source_type="PUBMED_LITERATURE", primary_ref="PMID:15218094",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="H3 antigenic-map literature",
         title="Mapping the antigenic and genetic evolution of influenza virus.",
         published_on="2004-07-16", topics=("reference-strain", "published-table"),
         review_status="accepted",
         archive_note="Cited as a published article title. This snapshot does not recompute an antigenic map or an evolutionary model."),
    dict(evidence_id="EV-REF-PETROVA", source_type="PUBMED_LITERATURE", primary_ref="PMID:29081496",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="seasonal influenza review literature",
         title="The evolution of seasonal influenza viruses.",
         published_on=None, topics=("reference-strain",),
         review_status="accepted",
         archive_note="NCBI esummary pubdate is 2018 Jan (month precision). Title citation only."),
    dict(evidence_id="EV-REF-CALHA", source_type="PUBMED_LITERATURE", primary_ref="PMID:23110350",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="A/California/07/2009 recombinant HA literature",
         title="Pandemic influenza vaccine: characterization of A/California/07/2009 (H1N1) recombinant hemagglutinin protein and insights into H1N1 antigen stability.",
         published_on="2012-10-30", topics=("reference-strain", "h1n1pdm09"),
         review_status="accepted",
         archive_note="NCBI esummary pubdate 2012 Oct 30. Title citation only."),
    dict(evidence_id="EV-CONS-GILES", source_type="PUBMED_LITERATURE", primary_ref="PMID:21320540",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="H5N1 consensus-sequence literature",
         title="A computationally optimized broadly reactive antigen (COBRA) based H5N1 VLP vaccine elicits broadly reactive antibodies in mice and ferrets.",
         published_on="2011-04-05", topics=("consensus-sequence", "h5n1"),
         review_status="accepted",
         archive_note="Title citation only. No consensus sequence, alignment, or computed score is stored."),
    dict(evidence_id="EV-CONS-CARTER", source_type="PUBMED_LITERATURE", primary_ref="PMID:26912624",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="H1N1 consensus-sequence literature",
         title="Design and Characterization of a Computationally Optimized Broadly Reactive Hemagglutinin Vaccine for H1N1 Influenza Viruses.",
         published_on=None, topics=("consensus-sequence", "h1n1"),
         review_status="flagged",
         archive_note="PubMed pubdate is 2016 May (month precision). A later PubMed record PMID:38819164 is titled as a correction to this article. This capsule stores the original title only and does not restate correction details."),
    dict(evidence_id="EV-CONS-CARTER-CORR", source_type="PUBMED_LITERATURE", primary_ref="PMID:38819164",
         dataset_version=V2, ingested_at=AT_V2, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="H1N1 consensus-sequence correction notice",
         title='Correction for Carter et al., "Design and Characterization of a Computationally Optimized Broadly Reactive Hemagglutinin Vaccine for H1N1 Influenza Viruses".',
         published_on="2024-07-23", topics=("consensus-sequence", "h1n1"),
         review_status="accepted",
         archive_note="PubMed lists this item as a correction to PMID:26912624. The abstract field was empty in the 2026-11-28 efetch. This capsule stores the correction title only."),
    dict(evidence_id="EV-GLY-WANG", source_type="PUBMED_LITERATURE", primary_ref="PMID:19822741",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="HA glycosylation literature",
         title="Glycans on influenza hemagglutinin affect receptor binding and immune response.",
         published_on="2009-10-27", topics=("head-glycosylation",),
         review_status="accepted",
         archive_note="Title citation only. No glycosylation-site edit, glycan recipe, or binding energy is stored."),
    dict(evidence_id="EV-GLY-TATE", source_type="PUBMED_LITERATURE", primary_ref="PMID:24638204",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="HA glycosylation literature",
         title="Playing hide and seek: how glycosylation of the influenza virus hemagglutinin can modulate the immune response to infection.",
         published_on="2014-03-14", topics=("head-glycosylation",),
         review_status="accepted",
         archive_note="NCBI esummary pubdate 2014 Mar 14. Title citation only."),
    dict(evidence_id="EV-GLY-ADD", source_type="PUBMED_LITERATURE", primary_ref="PMID:23365085",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="H1N1pdm09 HA glycosylation literature",
         title="Addition of glycosylation to influenza A virus hemagglutinin modulates antibody-mediated recognition of H1N1 2009 pandemic viruses.",
         published_on="2013-03-01", topics=("head-glycosylation", "h1n1pdm09"),
         review_status="accepted",
         archive_note="NCBI esummary pubdate 2013 Mar 1. Title citation only."),
    dict(evidence_id="EV-STEM-IMP", source_type="PUBMED_LITERATURE", primary_ref="PMID:26303961",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="HA stem immunogen literature",
         title="A stable trimeric influenza hemagglutinin stem as a broadly protective immunogen.",
         published_on="2015-09-18", topics=("conserved-stem",),
         review_status="accepted",
         archive_note="NCBI esummary pubdate 2015 Sep 18. The title is quoted verbatim and is not an efficacy conclusion of this prototype."),
    dict(evidence_id="EV-STEM-YASSINE", source_type="PUBMED_LITERATURE", primary_ref="PMID:26301691",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="HA stem immunogen literature",
         title="Hemagglutinin-stem nanoparticles generate heterosubtypic influenza protection.",
         published_on=None, topics=("conserved-stem",),
         review_status="accepted",
         archive_note="NCBI esummary pubdate is 2015 Sep (month precision). The title is stored verbatim and is not an efficacy conclusion of this prototype."),
    dict(evidence_id="EV-STEM-EKIERT", source_type="PUBMED_LITERATURE", primary_ref="PMID:19251591",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="HA stem antibody literature",
         title="Antibody recognition of a highly conserved influenza virus epitope.",
         published_on="2009-04-10", topics=("conserved-stem",),
         review_status="accepted",
         archive_note="NCBI esummary pubdate 2009 Apr 10. Title citation only."),
    dict(evidence_id="EV-STEM-HEADLESS", source_type="PUBMED_LITERATURE", primary_ref="PMID:26947245",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="HA stem immunogen literature",
         title="Stalking influenza by vaccination with pre-fusion headless HA mini-stem.",
         published_on="2016-03-07", topics=("conserved-stem",),
         review_status="accepted",
         archive_note="NCBI esummary pubdate 2016 Mar 7. Title citation only. No construct sequence is stored."),
    dict(evidence_id="EV-STEM-STALK", source_type="PUBMED_LITERATURE", primary_ref="PMID:25210189",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="HA stalk antibody literature",
         title="Induction of broadly reactive anti-hemagglutinin stalk antibodies by an H5N1 vaccine in humans.",
         published_on=None, topics=("conserved-stem", "h5n1"),
         review_status="accepted",
         archive_note="NCBI esummary pubdate is 2014 Nov (month precision). Title citation only."),
    dict(evidence_id="EV-ACC-CA07", source_type="NCBI_NUCCORE", primary_ref="Accession:CY121680.1",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T2_SURVEILLANCE",
         subtype_context="A/California/07/2009 HA nuccore metadata",
         title="Influenza A virus (A/California/07/2009(H1N1)) hemagglutinin (HA) gene, complete cds",
         published_on=None, topics=("reference-strain", "h1n1pdm09"),
         review_status="accepted",
         archive_note="NCBI nuccore createdate and updatedate 2012/06/20; slen 1752. The nucleotide sequence is not stored."),
    dict(evidence_id="EV-ACC-HK68", source_type="NCBI_NUCCORE", primary_ref="Accession:AF348176.1",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T2_SURVEILLANCE",
         subtype_context="A/Hong Kong/1/1968 HA nuccore metadata",
         title="Influenza A virus (A/Hong Kong/1/68(H3N2)) hemagglutinin gene, complete cds",
         published_on=None, topics=("reference-strain", "h3n2"),
         review_status="accepted",
         archive_note="NCBI nuccore createdate 2001/05/09; updatedate 2001/06/07; slen 1736. The nucleotide sequence is not stored."),
    dict(evidence_id="EV-PDB-3GBN", source_type="PDB_STRUCTURE", primary_ref="PDB:3GBN",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T1_WET_LAB_ASSAY",
         subtype_context="RCSB structure deposit, 1918 H1 HA with CR6261",
         title="Crystal Structure of Fab CR6261 in Complex with the 1918 H1N1 influenza virus hemagglutinin",
         published_on="2009-03-10", topics=("conserved-stem", "structure-deposit"),
         review_status="accepted",
         archive_note="RCSB initial_release_date 2009-03-10; method X-RAY DIFFRACTION. Resolution is omitted; it is not a performance score."),
    dict(evidence_id="EV-PDB-3GBM", source_type="PDB_STRUCTURE", primary_ref="PDB:3GBM",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T1_WET_LAB_ASSAY",
         subtype_context="RCSB structure deposit, H5 HA with CR6261",
         title="Crystal Structure of Fab CR6261 in Complex with a H5N1 influenza virus hemagglutinin.",
         published_on="2009-03-10", topics=("conserved-stem", "structure-deposit"),
         review_status="accepted",
         archive_note="RCSB initial_release_date 2009-03-10; method X-RAY DIFFRACTION. Deposit title includes the trailing period."),
    dict(evidence_id="EV-PDB-5C0S", source_type="PDB_STRUCTURE", primary_ref="PDB:5C0S",
         dataset_version=V2, ingested_at=AT_V2, evidence_tier="T1_WET_LAB_ASSAY",
         subtype_context="RCSB structure deposit, generation-4 HA stem",
         title="Crystal structure of a generation 4 influenza hemagglutinin stabilized stem in complex with the broadly neutralizing antibody CR6261",
         published_on="2015-09-02", topics=("conserved-stem", "structure-deposit"),
         review_status="accepted",
         archive_note="RCSB initial_release_date 2015-09-02; method X-RAY DIFFRACTION. No designed sequence is stored."),
    dict(evidence_id="EV-PDB-5C0R", source_type="PDB_STRUCTURE", primary_ref="PDB:5C0R",
         dataset_version=V2, ingested_at=AT_V2, evidence_tier="T1_WET_LAB_ASSAY",
         subtype_context="RCSB structure deposit, generation-3 HA stem",
         title="Crystal Structure of a Generation 3 Influenza Hemagglutinin Stabilized Stem Complexed with the Broadly Neutralizing Antibody C179",
         published_on="2015-09-02", topics=("conserved-stem", "structure-deposit"),
         review_status="accepted",
         archive_note="RCSB initial_release_date 2015-09-02; method X-RAY DIFFRACTION."),
    dict(evidence_id="EV-IEDB-570", source_type="IEDB_EPITOPE", primary_ref="IEDB:570",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T1_WET_LAB_ASSAY",
         subtype_context="IEDB linear HA epitope record",
         title="ACKRGPGSGFFSRLN is a linear peptidic epitope (epitope ID 570) studied as part of Hemagglutinin (UniProt:P03452) from Influenza A virus.  This epitope has been studied for immune reactivity in 2 publication(s), tested in 4 T cell assays and 7 B cell assays.",
         published_on=None, topics=("hemagglutinin", "iedb-epitope"),
         review_status="accepted",
         archive_note="Verbatim epitope_summary from query-api.iedb.org on 2026-11-28. The peptide text is the database summary, not a construct designed here. Assay steps are not stored."),
    dict(evidence_id="EV-IEDB-226309", source_type="IEDB_EPITOPE", primary_ref="IEDB:226309",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T1_WET_LAB_ASSAY",
         subtype_context="IEDB discontinuous HA epitope record citing 3gbn",
         title="A: H25, H45, V46, N47, L496, S306, L307, P308, T333; B: D363, G364, W365, Q382, T385, Q386, I389, D390, T393, V396, N397, I400; is a discontinuous epitope (epitope ID 226309) studied as part of Two components:Hemagglutinin (UniProt:P03452) & Hemagglutinin (UniProt:P03452) from Influenza A virus.  This epitope has been studied for immune reactivity in 4 publication(s), tested in 12 B cell assays and has 3D structure(s) 3gbn.",
         published_on=None, topics=("conserved-stem", "iedb-epitope"),
         review_status="accepted",
         archive_note="Verbatim epitope_summary from query-api.iedb.org on 2026-11-28. Residue tokens are the IEDB summary, not a site-engineering instruction."),
    dict(evidence_id="EV-UP-P03452", source_type="UNIPROT_RECORD", primary_ref="UniProt:P03452",
         dataset_version=V1, ingested_at=AT_V1, evidence_tier="T3_PEER_REVIEWED_LIT",
         subtype_context="UniProt reviewed HA entry for A/Puerto Rico/8/1934",
         title=">sp|P03452|HEMA_I34A1 Hemagglutinin OS=Influenza A virus (strain A/Puerto Rico/8/1934 H1N1) OX=211044 GN=HA PE=1 SV=2",
         published_on=None, topics=("reference-strain", "hemagglutinin"),
         review_status="accepted",
         archive_note="First line of the UniProt FASTA retrieved 2026-11-28. The amino-acid sequence is not stored. Tier T3 marks a curated reference entry, not a journal article and not a new computation."),
)

QUESTIONS = (
    ("PMID:19465683 的公开题名对应哪一条参考株文献？", ("EV-REF-GARTEN",)),
    ("Glycans on influenza hemagglutinin affect receptor binding and immune response 是哪一条已发表题名？ PMID:19822741",
     ("EV-GLY-WANG",)),
    ("H1N1 共识序列文献 PMID:26912624 与其更正通知 PMID:38819164 分别是哪两条记录？",
     ("EV-CONS-CARTER", "EV-CONS-CARTER-CORR")),
    ("RCSB 登录 PDB:3GBN 与 PDB:5C0S 分别对应哪两条结构记录？", ("EV-PDB-3GBN", "EV-PDB-5C0S")),
    ("NCBI Accession:CY121680.1 的血凝素定义行是什么？", ("EV-ACC-CA07",)),
    ("Stalking influenza by vaccination with pre-fusion headless HA mini-stem 这条已发表题名在库中吗？",
     ("EV-STEM-HEADLESS",)),
    ("IEDB:570 与 IEDB:226309 的表位摘要原文是什么？", ("EV-IEDB-570", "EV-IEDB-226309")),
)

DOSSIERS = (
    dict(dossier_id="plan-reference-strain", label="参考株文献与登录号", version=V1,
         source_ref="PMID:19465683", review_status="accepted",
         annotation="已发表参考株文献与公共登录号元数据。不含序列，不含新的生物学评分。",
         citations=("EV-REF-GARTEN", "EV-REF-SMITH", "EV-REF-PETROVA", "EV-REF-CALHA",
                    "EV-ACC-CA07", "EV-ACC-HK68", "EV-UP-P03452")),
    dict(dossier_id="plan-consensus-literature", label="共识序列文献", version=V1,
         source_ref="PMID:21320540", review_status="flagged",
         annotation="已发表共识序列文献与一条更正通知。不保存共识序列，不计算新分数。",
         citations=("EV-CONS-GILES", "EV-CONS-CARTER", "EV-CONS-CARTER-CORR")),
    dict(dossier_id="plan-head-glycosylation", label="头部糖基化文献", version=V1,
         source_ref="PMID:19822741", review_status="accepted",
         annotation="已发表糖基化文献题名。不是糖基化位点改造，也不是实验步骤清单。",
         citations=("EV-GLY-WANG", "EV-GLY-TATE", "EV-GLY-ADD")),
    dict(dossier_id="plan-conserved-stem", label="保守茎部文献与结构登录", version=V2,
         source_ref="PDB:5C0S", review_status="accepted",
         annotation="已发表茎部文献、RCSB 结构登录和 IEDB 摘要。不保存构建体序列。",
         citations=("EV-STEM-IMP", "EV-STEM-YASSINE", "EV-STEM-EKIERT", "EV-STEM-HEADLESS",
                    "EV-STEM-STALK", "EV-PDB-3GBN", "EV-PDB-3GBM", "EV-PDB-5C0S",
                    "EV-PDB-5C0R", "EV-IEDB-570", "EV-IEDB-226309")),
)

# Hand-listed gold for the deterministic archive-note and tier rules. Not a biological score.
GOLD = {
    "plan-reference-strain": {
        "conflicts": [],
        "gaps": ["no_T1_record"],
        "consistent": True,
    },
    "plan-consensus-literature": {
        "conflicts": [["PMID:26912624", "PMID:38819164"]],
        "gaps": ["version_mismatch", "dossier_review_open", "source_review_open",
                 "no_T1_record", "no_T2_record"],
        "consistent": False,
    },
    "plan-head-glycosylation": {
        "conflicts": [],
        "gaps": ["no_T1_record", "no_T2_record"],
        "consistent": True,
    },
    "plan-conserved-stem": {
        "conflicts": [],
        "gaps": ["version_mismatch", "no_T2_record"],
        "consistent": False,
    },
}

DECLINED = (
    "GISAID sequences and counts",
    "Nextstrain clade-frequency tables",
    "Bloom Lab deep-mutational-scan escape or fitness scores",
    "nucleotide sequences and designed amino-acid constructs",
    "wet-lab protocols and experimental recipes",
    "new immunogenicity, protection, or clinical scores",
    "timed human SOP (left as 未测)",
)


def _by_id():
    return {row["evidence_id"]: row for row in RECORDS}


def capsule_row(spec: dict) -> dict:
    snippet = spec["title"]
    return {
        "evidence_id": spec["evidence_id"],
        "source_type": spec["source_type"],
        "primary_ref": spec["primary_ref"],
        "dataset_version": spec["dataset_version"],
        "ingested_at": spec["ingested_at"],
        "evidence_tier": spec["evidence_tier"],
        "subtype_context": spec["subtype_context"],
        "claim_summary": f"{spec['primary_ref']} {spec['subtype_context']}. {CITE}",
        "raw_snippet": snippet,
        "sha256": digest(snippet.encode()),
    }


def lock_entry(spec: dict, row: dict) -> dict:
    return {
        "evidence_id": spec["evidence_id"],
        "dataset_version": spec["dataset_version"],
        "record_sha256": digest(canonical(row)),
        "title": spec["title"],
        "primary_ref": spec["primary_ref"],
        "source_url": database_source_url(spec["primary_ref"]) or f"https://pubmed.ncbi.nlm.nih.gov/{spec['primary_ref'].split(':', 1)[1]}/",
        "nature": "public_database" if spec["source_type"] != "PUBMED_LITERATURE" else "public_methods",
        "approval": "approved",
        "review_status": spec["review_status"],
        "topics": list(spec["topics"]),
        "published_on": spec["published_on"],
        "archive_note": spec["archive_note"],
    }


def release_lock() -> dict:
    rows = [capsule_row(spec) for spec in RECORDS]
    return {
        "tenant_id": "demo",
        "scope": "methods-and-records-governance",
        "records": [lock_entry(spec, row) for spec, row in zip(RECORDS, rows)],
        "releases": [
            {"dataset_version": V1, "released_at": "2026-11-28T06:30:00+08:00"},
            {"dataset_version": V2, "released_at": "2026-11-28T09:30:00+08:00", "previous_version": V1},
        ],
    }


def dataset_card(lock: dict) -> str:
    lines = [
        "# FluEvidenceBench-v1 数据集说明",
        "",
        "软件原型用的离线证据快照。每条记录都是已发表题名、NCBI 定义行、RCSB 题名、IEDB `epitope_summary` 或 UniProt FASTA 首行。",
        "本数据集不提供湿实验步骤、构建体序列、逃逸或适应度预测，也不把文献题名里的结果用语当作临床或保护效果结论。",
        "",
        f"- 数据版本：`{V1}`，以及增补更正通知与两条茎部结构登录的 `{V2}`。",
        "- 审核范围：`methods-and-records-governance`。租户：`demo`。",
        "- 标识核验日期：2026-11-28。来源是当时的 NCBI esummary/efetch、RCSB Data API、IEDB query API 和 UniProt FASTA 首行。",
        "- 证据等级映射：IEDB 与 RCSB 实验登录记为 `T1_WET_LAB_ASSAY`（公开实验记录，不是复现的实验步骤）；NCBI nuccore 元数据记为 `T2_SURVEILLANCE`；PubMed 题名记为 `T3_PEER_REVIEWED_LIT`；UniProt 已审校蛋白条目也记为 T3，表示它是蛋白质数据库中的审校记录，不是期刊论文，也不是新的计算结果。",
        "- `T4_COMPUTATIONAL` 计数为 0。深度突变扫描、逃逸分数和适应度预测没有入库。",
        "",
        "## 未入库",
        "",
    ]
    lines.extend(f"- {item}" for item in DECLINED)
    lines.extend(["", "## 记录", "",
                  "| evidence_id | primary_ref | source_type | dataset_version | ingested_at | evidence_tier | published_on | review_status |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    specs = _by_id()
    for entry in lock["records"]:
        spec = specs[entry["evidence_id"]]
        lines.append(
            f"| {spec['evidence_id']} | {spec['primary_ref']} | {spec['source_type']} | "
            f"{spec['dataset_version']} | {spec['ingested_at']} | {spec['evidence_tier']} | "
            f"{spec['published_on'] or '未提供精确日'} | {entry['review_status']} |")
    lines.extend([
        "",
        "## 任务",
        "",
        "Task-1 是证据问答。每题给出必须召回的 evidence_id，问题里使用公开题名或公开 ID，答案只能引用上表原文。",
        "Task-2 比较四份已经发表的候选方案文献档案：参考株、共识序列文献、头部糖基化文献、保守茎部文献。",
        "比较维度是来源覆盖、版本一致性、引用交叉（档案注释里点名另一条公开 ID）、T1–T4 分布，以及证据空白。证据空白包括缺 T1/T2 记录、版本不一致和审阅未关闭。它不是实验清单，也不是新的生物学性能分数。",
        "",
        "人工检索 SOP 没有计时，记为未测。",
        "",
    ])
    return "\n".join(lines)


def materialize(root: Path = BENCH) -> Snapshot:
    root.mkdir(parents=True, exist_ok=True)
    rows = [capsule_row(spec) for spec in RECORDS]
    lock = release_lock()
    jsonl_dir, parquet_dir = root / "jsonl", root / "parquet"
    jsonl_dir.mkdir(exist_ok=True)
    parquet_dir.mkdir(exist_ok=True)
    (jsonl_dir / "evidence.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    import pyarrow as pa
    import pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist(rows), parquet_dir / "evidence.parquet")
    (root / "release.lock.json").write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "DATASET_CARD.md").write_text(dataset_card(lock), encoding="utf-8")
    tasks = {
        "dataset_version": V2,
        "questions": [{"query": query, "required": list(required)} for query, required in QUESTIONS],
        "dossiers": [{**spec, "citations": list(spec["citations"])} for spec in DOSSIERS],
        "gold": GOLD,
        "declined": list(DECLINED),
        "manual_sop_baseline": "未测",
    }
    (root / "tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return Snapshot(jsonl_dir, root / "release.lock.json")


def dossier_bodies(snapshot: Snapshot) -> list[dict]:
    index = _by_id()
    bodies = []
    for spec in DOSSIERS:
        citations = [{"evidence_id": evidence_id, "dataset_version": index[evidence_id]["dataset_version"]}
                     for evidence_id in spec["citations"]]
        body = {key: spec[key] for key in ("dossier_id", "label", "version", "source_ref", "review_status", "annotation")}
        body["citations"] = citations
        body["archive_sha256"] = archive_digest(Dossier.model_validate(body))
        bodies.append(body)
    return bodies


def _svg(title: str, rows: list[tuple[str, float]], unit: str) -> str:
    width, height, left, top = 760, 48 + 28 * max(len(rows), 1), 280, 36
    peak = max((value for _label, value in rows), default=1) or 1
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img">',
             f'<title>{title}</title>',
             '<rect width="100%" height="100%" fill="#f7fbfd"/>',
             f'<text x="16" y="22" font-family="sans-serif" font-size="14" fill="#173246">{title}</text>']
    for index, (label, value) in enumerate(rows):
        y = top + index * 28
        bar = (width - left - 80) * value / peak
        parts.append(f'<text x="16" y="{y + 12}" font-family="sans-serif" font-size="12" fill="#245">{label}</text>')
        parts.append(f'<rect x="{left}" y="{y}" width="{bar:.1f}" height="16" fill="#216b8b"/>')
        parts.append(f'<text x="{left + bar + 8:.1f}" y="{y + 12}" font-family="sans-serif" font-size="12" fill="#245">{value:.3f}{unit}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def write_charts(metrics: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "recall_at_5.svg").write_text(_svg(
        "Task-1 Recall@5（封闭题，题面含公开题名或公开 ID）",
        [(row["question_id"], row["recall_at_5"]) for row in metrics["task_1"]["per_question"]], ""), encoding="utf-8")
    (directory / "latency_ms.svg").write_text(_svg(
        "测得延迟（毫秒）",
        [("Task-1 中位", metrics["task_1"]["median_ms"]), ("Task-2 比较", metrics["task_2"]["compare_ms"]),
         ("签批", metrics["task_2"]["signoff_ms"])], " ms"), encoding="utf-8")
    (directory / "gaps.svg").write_text(_svg(
        "Task-2 证据空白条数（不是实验清单）",
        [(row["dossier_id"], row["gap_count"]) for row in metrics["task_2"]["per_dossier"]], ""), encoding="utf-8")


def _post(client, route: str, body: dict):
    start = perf_counter_ns()
    response = client.post(f"/api/v1/{route}", json=body)
    elapsed = (perf_counter_ns() - start) / 1e6
    response.raise_for_status()
    return response.json(), elapsed


class NoRetrievalDraft(BaseLLMClient):
    """Offline contrast: a draft that does not quote the retrieved record."""

    def assemble(self, query, records):
        original = records[0]
        return [Citation("EV-NOT-IN-LOCK", original.dataset_version, original.raw_snippet),
                Citation(original.evidence_id, "flu-evidence-missing", original.raw_snippet),
                Citation(*original.key, "Guaranteed protection")]


def run_bench(snapshot: Snapshot | None = None) -> tuple[dict, dict]:
    from fastapi.testclient import TestClient
    from server import create_app

    with offline_runtime():
        snapshot = snapshot or Snapshot(BENCH / "jsonl", BENCH / "release.lock.json")
        models = TextModels()
        dossiers = dossier_bodies(snapshot)
        with TestClient(create_app(snapshot, models=models)) as client:
            manifest = client.get("/api/v1/health").json()
            qa_runs = []
            for index, (query, required) in enumerate(QUESTIONS, 1):
                report, elapsed = _post(client, "qa", {"query": query, "limit": 5, "hops": 3})
                hits = [item["evidence_id"] for item in report["retrieval"]]
                relevant = set(required)
                qa_runs.append({
                    "question_id": f"Q{index}", "query": query, "expected": list(required),
                    "hits": hits, "recall_at_5": len(relevant & set(hits)) / len(relevant),
                    "ndcg_at_5": ndcg([int(hit in relevant) for hit in hits], [1] * len(relevant), 5),
                    "elapsed_ms": elapsed, "report": report,
                })
            compare, compare_ms = _post(client, "compare", {"dossiers": dossiers, "period": "quarter", "hops": 2})
            actions = []
            for statement in compare["statements"]:
                action = "flag_doubt" if statement["evidence_id"] == "EV-CONS-CARTER" else "accept"
                actions.append({"statement_id": statement["statement_id"], "action": action,
                                "note": "离线签批演示。不采纳为疗效结论。"})
            review, review_ms = _post(client, "review/signoff", {
                "report_id": compare["report_id"], "expected_version": 1,
                "reviewer": "demo-reviewer", "actions": actions, "signoff": True,
            })
        with TestClient(create_app(snapshot, client=NoRetrievalDraft(), models=models)) as blinded:
            blinded_report, _elapsed = _post(blinded, "qa", {"query": QUESTIONS[0][0], "limit": 1})
        probe = snapshot.records[("EV-REF-GARTEN", V1)].model_copy(update={
            "raw_snippet": "Guaranteed protection",
            "sha256": digest(b"Guaranteed protection"),
        })
        from engine.audit import audit
        _statements, probe_rejected = audit([Citation(*probe.key, probe.raw_snippet)], [probe])

    snippets = [record.raw_snippet for record in snapshot.records.values()]
    statements = [statement for row in qa_runs for statement in row["report"]["statements"]]
    statements.extend(compare["statements"])
    matched = 0
    for statement in statements:
        record = snapshot.records.get((statement["evidence_id"], statement["dataset_version"]))
        matched += bool(record and record.raw_snippet == statement["text"] and record.primary_ref == statement["primary_ref"])
    per_dossier = []
    for row in compare["dossier_matrix"]:
        dimensions = row["evidence_dimensions"]
        predicted = [list(pair) for pair in sorted(
            (item["left_ref"], item["right_ref"]) for item in dimensions["citation_conflicts"])]
        gold = GOLD[row["dossier_id"]]
        per_dossier.append({
            "dossier_id": row["dossier_id"],
            "consistent": row["version_consistency"]["consistent"],
            "conflicts": predicted,
            "gaps": dimensions["evidence_gaps"],
            "tier_distribution": dimensions["tier_distribution"],
            "source_types_present": dimensions["source_types_present"],
            "gap_count": len(dimensions["evidence_gaps"]),
            "conflict_match": predicted == gold["conflicts"],
            "gap_match": dimensions["evidence_gaps"] == gold["gaps"],
            "consistent_match": row["version_consistency"]["consistent"] is gold["consistent"],
        })
    flagged = sum(item["conflict_match"] and item["gap_match"] and item["consistent_match"] for item in per_dossier)
    metrics = {
        "scope": "FluEvidenceBench-v1 software prototype",
        "dataset_version": V2,
        "snapshot_id": manifest["snapshot_id"],
        "record_count": manifest["record_count"],
        "task_1": {
            "k": 5, "queries": len(qa_runs),
            "recall_at_5": mean(row["recall_at_5"] for row in qa_runs),
            "ndcg_at_5": mean(row["ndcg_at_5"] for row in qa_runs),
            "median_ms": median(row["elapsed_ms"] for row in qa_runs),
            "per_question": [{key: row[key] for key in ("question_id", "recall_at_5", "ndcg_at_5", "elapsed_ms", "expected", "hits")}
                             for row in qa_runs],
            "note": "封闭题面包含公开题名或公开 ID。这是该题集上的测得召回，不是赛题目标值。",
        },
        "task_2": {
            "dossiers": len(per_dossier),
            "compare_ms": compare_ms, "signoff_ms": review_ms,
            "signed_state": review["report"]["state"],
            "accepted_citations": sum(action["action"] == "accept" for action in actions),
            "flagged_citations": sum(action["action"] == "flag_doubt" for action in actions),
            "dossiers_matching_gold": flagged,
            "per_dossier": per_dossier,
            "note": "冲突标记只识别档案注释中的公开 ID 交叉引用。空白是缺等级、版本不一致或审阅未关闭。不是生物学性能，也不是实验清单。",
        },
        "citations": {
            "accepted_matching_lock": matched,
            "accepted_total": len(statements),
            "accuracy_among_accepted": matched / len(statements) if statements else 0,
            "note": "准确率只统计已经通过原文与版本锁的语句。被拒绝的草稿另行计数，不记为正确引用。",
        },
        "no_retrieval_baseline": {
            "submitted": 3,
            "accepted_statements": len(blinded_report["statements"]),
            "rejected": blinded_report["agent_trace"][-1]["rejected"],
            "note": "不读取快照原文的离线草稿，仅用于对照幻觉拦截。",
        },
        "compliance_gate": {
            "stored_snippets": len(snippets),
            "stored_snippets_matching_effect_promise": sum(bool(_EFFECT_PROMISE.search(text)) for text in snippets),
            "accepted_statements_matching_effect_promise": sum(bool(_EFFECT_PROMISE.search(row["text"])) for row in statements),
            "probe_submitted": 1,
            "probe_effect_promise_rejected": probe_rejected["effect_promise"],
            "probe_accepted": len(_statements),
        },
        "manual_sop_baseline": "未测",
        "declined": list(DECLINED),
    }
    bundle = {"snapshot": manifest, "qa": qa_runs, "dossiers": dossiers, "compare": compare,
              "signoff": review, "blinded": blinded_report, "metrics": metrics}
    return bundle, metrics


def write_eval(metrics: dict, directory: Path | None = None) -> Path:
    directory = directory or BENCH / "eval"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (directory / "task1_recall.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, ["question_id", "recall_at_5", "ndcg_at_5", "elapsed_ms", "expected", "hits"])
        writer.writeheader()
        for row in metrics["task_1"]["per_question"]:
            writer.writerow({**row, "expected": " ".join(row["expected"]), "hits": " ".join(row["hits"])})
    with (directory / "task2_dossiers.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["dossier_id", "consistent", "gap_count", "gaps", "conflicts", "gap_match", "conflict_match", "consistent_match"]
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for row in metrics["task_2"]["per_dossier"]:
            writer.writerow({**{key: row[key] for key in fields},
                             "gaps": " ".join(row["gaps"]),
                             "conflicts": ";".join(" ".join(pair) for pair in row["conflicts"])})
    write_charts(metrics, directory)
    return directory


def workbench_document(bundle: dict, metrics: dict) -> dict:
    from engine.audit import BOUNDARY
    compare = bundle["compare"]
    questions = []
    for row in bundle["qa"]:
        questions.append({
            "question_id": row["question_id"], "query": row["query"], "expected": row["expected"],
            "hits": row["hits"], "recall_at_5": row["recall_at_5"], "elapsed_ms": row["elapsed_ms"],
            "statements": row["report"]["statements"],
            "agent_trace": row["report"]["agent_trace"],
        })
    signoff = bundle["signoff"]
    return {
        "boundary": BOUNDARY,
        "product": "流盾智研（FluVax-Evidence Agent）",
        "dataset_version": V2,
        "snapshot_id": bundle["snapshot"]["snapshot_id"],
        "releases": bundle["snapshot"]["releases"],
        "record_count": bundle["snapshot"]["record_count"],
        "records": [],
        "timeline": compare["metadata_timeline"],
        "questions": questions,
        "dossiers": compare["dossier_matrix"],
        "signoff": {
            "state": signoff["report"]["state"],
            "version": signoff["report"]["version"],
            "markdown": signoff["exports"]["markdown"],
            "evidence_csv": signoff["exports"]["evidence_csv"],
            "statements": [{**statement, "disposition": signoff["report"]["review"].get(statement["statement_id"])}
                           for statement in signoff["report"]["statements"]],
        },
        "metrics": metrics,
        "charts": [
            {"id": "recall", "title": "Task-1 Recall@5", "kind": "bar",
             "axes": [{"label": row["question_id"]} for row in metrics["task_1"]["per_question"]],
             "series": [{"name": "Recall@5", "values": [row["recall_at_5"] for row in metrics["task_1"]["per_question"]]}]},
            {"id": "latency", "title": "测得延迟（毫秒）", "kind": "bar",
             "axes": [{"label": "问答中位"}, {"label": "比较"}, {"label": "签批"}],
             "series": [{"name": "毫秒", "values": [metrics["task_1"]["median_ms"], metrics["task_2"]["compare_ms"], metrics["task_2"]["signoff_ms"]]}]},
            {"id": "dimensions", "title": "证据治理五维（不是免疫原性能）", "kind": "radar",
             "axes": [{"label": "来源覆盖", "maximum": 1}, {"label": "版本一致", "maximum": 1},
                      {"label": "引用无交叉冲突", "maximum": 1}, {"label": "等级覆盖", "maximum": 1},
                      {"label": "未决事项少", "maximum": 1}],
             "series": [{"name": row["label"], "values": [row["evidence_dimensions"][key] for key in (
                 "source_coverage", "version_consistency", "citation_conflict_clearance",
                 "tier_breadth", "open_review_clearance")]} for row in compare["dossier_matrix"]]},
        ],
        "manual_sop_baseline": "未测",
        "declined": list(DECLINED),
        "score_note": compare["dossier_matrix"][0]["evidence_dimensions"]["note"],
    }


def export_workbench(document: dict) -> None:
    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    targets = [ROOT / "frontend_demo_data" / "fluvax_workbench.json",
               ROOT.parent / "shared-workbench" / "frontend" / "public" / "fluvax" / "workbench.json"]
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")


def attach_records(document: dict, snapshot: Snapshot) -> dict:
    document["records"] = [{
        "evidence_id": record.evidence_id,
        "dataset_version": record.dataset_version,
        "primary_ref": record.primary_ref,
        "source_type": record.source_type,
        "source_url": snapshot.metadata[record.key].source_url,
        "evidence_tier": record.evidence_tier,
        "ingested_at": record.ingested_at,
        "published_on": snapshot.metadata[record.key].published_on,
        "review_status": snapshot.metadata[record.key].review_status,
        "title": snapshot.metadata[record.key].title,
        "raw_snippet": record.raw_snippet,
        "claim_summary": record.claim_summary,
        "topics": list(snapshot.metadata[record.key].topics),
        "nature": snapshot.metadata[record.key].nature,
        "subtype_context": record.subtype_context,
    } for record in snapshot.records.values()]
    return document


if __name__ == "__main__":
    snapshot = materialize()
    bundle, metrics = run_bench(snapshot)
    write_eval(metrics)
    export_workbench(attach_records(workbench_document(bundle, metrics), snapshot))
    print(json.dumps({key: metrics[key] for key in (
        "record_count", "task_1", "task_2", "citations", "no_retrieval_baseline",
        "compliance_gate", "manual_sop_baseline")}, ensure_ascii=False, indent=2))
