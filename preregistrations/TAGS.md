# Tags

The tags live in the lab's private repository. Where a tag has a stamped text, it is timestamped with OpenTimestamps; the proofs are in `reports/qaoa-explore-anchors/` and `reports/p0d-anchors/`.

| Tag | Tag object | Commit | Published here | Timestamp proof |
|---|---|---|---|---|
| `qaoa-prereg` | `9a9d4ca3d4ade09d03c4df8220bdc7169191f632` | `1e6d9b1360efcbc58cb412bcf6106a29755e90ea` | `P0e-qaoa-explore.md`, byte for byte from the tag | Yes |
| `qaoa-freeze` | `37d53ee9c1dd2148e2f1ab346c6063f0dc694cf4` | `68b0b1c7490832f9188f4eaa3e452b7aec1d86f3` | `search_config.json`, whose sha256 is in the stamped text | Yes |
| `audit-prereg` | none (a lightweight tag) | `beb88972f4b568887bf69f7e763d5c8335371e46` | `P0b-audit-spike.md`, byte for byte from the tag | No |
| `audit-addendum` | `d3d4cbf4b8dc2f33219d099aa9716b29320b7a3f` | `b7717e60dd217f3f84fe4de5ee73d676e50d3541` | The plan file is identical at this tag; the addendum declared the QCEC 3.11.0 re-check, as the audit record describes | No |
| `p0d-prereg` | `2f451f2d380c45510dba278f50895277ad5e58f7` | `4091e70aa915eae2f4f60b30a0fa83a57299a410` | `P0d-model-triage.md`, byte for byte from the tag | Yes |

The audit's tags carry no timestamp proof, so their dates rest on the private repository and on our word.
