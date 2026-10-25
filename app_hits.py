p = "evidence-grounded-rag-frontend/src/App.jsx"
with open(p, "r", encoding="utf-8") as f:
    text = f.read()
lines = text.split("\n")
need = ("confidence", "nli", "support_basis", "verdict", "SUPPORTED", "NOT_ENOUGH", "CONTRADICTED")
hits = []
for i, l in enumerate(lines, 1):
    if any(k in l for k in need):
        hits.append(i)
print("hits:", hits)
out = []
for h in hits:
    out.append("----- line %d -----" % h)
    for j in range(max(1, h - 4), min(len(lines), h + 4) + 1):
        out.append("%5d: %s" % (j, lines[j - 1]))
with open("C:\\Users\\Masseeha\\AppData\\Local\\Temp\\opencode\\app_hits.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
