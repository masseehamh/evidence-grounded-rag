p = "evidence-grounded-rag-frontend/src/App.jsx"
with open(p, "r", encoding="utf-8") as f:
    text = f.read()
lines = text.split("\n")
for i in range(80, 100):
    print("%5d: %s" % (i, lines[i - 1]))
