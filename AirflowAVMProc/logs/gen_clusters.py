import json


def cu(site, nums):
    return ["r1%simdgcu%d" % (site, n) for n in nums]


def pw(site, nums):
    return ["r1%simdgpw%d" % (site, n) for n in nums]


def block_100(s):
    return {
        "CL1": cu(s, range(101, 111)) + pw(s, [101, 102, 103]),
        "CL2": cu(s, range(112, 122)) + pw(s, [104, 105, 106]),
        "CL3": cu(s, range(123, 133)) + pw(s, [107, 108, 109]),
        "CL4": cu(s, [134, 135]) + pw(s, [110, 111]),
        "CL5": cu(s, [145, 146]) + pw(s, [113, 114]),
        "CL6": cu(s, [155, 157]) + pw(s, [116, 117]),
        "CL7": cu(s, [167, 168]) + pw(s, [119, 120]),
    }


def block_200(s, with_cl7=True):
    d = {
        "CL1": cu(s, range(201, 211)) + pw(s, [201, 202, 203]),
        "CL2": cu(s, range(212, 222)) + pw(s, [204, 205, 206]),
        "CL3": cu(s, range(223, 233)) + pw(s, [207, 208, 209]),
        "CL4": cu(s, [234, 235]) + pw(s, [210, 211]),
        "CL5": cu(s, [245, 246]) + pw(s, [213, 214]),
        "CL6": cu(s, [256, 257]) + pw(s, [216, 217]),
    }
    if with_cl7:
        d["CL7"] = cu(s, [267, 268]) + pw(s, [219, 220])
    return d


def renum(d, start):
    ordered = sorted(d.items(), key=lambda x: int(x[0][2:]))
    return {"CL%d" % (start + i): v for i, (_, v) in enumerate(ordered)}


srb = {}
srb.update(block_100("srb"))
srb.update(renum(block_200("srb", False), 11))

mks = {}
mks.update(block_200("mks", True))
mks.update(renum(block_100("mks"), 11))
mks.pop("CL17", None)

data = {
    "fqdn_suffix": ".r1.telkomsel.co.id",
    "sites": {
        "SRB": {
            "display_name": "SRB NFT",
            "aliases": ["SRB", "SRB NFT", "SRB_NFT", "SRB_NFT_ADMIN", "SRBNFT"],
            "environment": "SRB_NFT_ADMIN",
            "clusters": srb,
        },
        "MKS": {
            "display_name": "MKS NFT",
            "aliases": ["MKS", "MKS NFT", "MKS_NFT", "MKS_NFT_ADMIN", "MKSNFT"],
            "environment": "MKS_NFT_ADMIN",
            "clusters": mks,
        },
    },
}

path = r"C:\GenAI\Cursor\mcps\AirflowAVMProc\tks_nft_clusters.json"
with open(path, "w", encoding="utf-8") as fh:
    fh.write(json.dumps(data, indent=2) + "\n")

for site in ("SRB", "MKS"):
    clusters = data["sites"][site]["clusters"]
    print(site, list(clusters), "VMs:", sum(len(v) for v in clusters.values()))
print("SRB CL6:", srb["CL6"])
print("SRB CL11:", srb["CL11"])
print("MKS CL7:", mks["CL7"])
print("MKS CL16:", mks["CL16"])
