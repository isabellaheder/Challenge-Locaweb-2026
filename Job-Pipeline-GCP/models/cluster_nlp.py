from pathlib import Path
import re
import unicodedata
import joblib
import numpy as np
import pandas as pd
from google.cloud import storage
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import (silhouette_score, davies_bouldin_score, calinski_harabasz_score)
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
try:
    from nltk.stem.snowball import SnowballStemmer
    STEMMER = SnowballStemmer("english")
except:
    STEMMER = None


ARQUIVO_SILVER = (
    "gs://predictops-silver/incidentes/"
    "incidentes_tratados.parquet")

BUCKET_GOLD = "predictops-gold"

Path("artifacts").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)

# stopwords
STOP = set("""
a an and as at be by com da das de do dos e em for from is na nas
no nos not o os ou para por que se sem the to um uma uns umas
was were with this that on of in are no yes alarm problem check
application monitoring error message host port time timeout high
low free space lack processor load backup disk unavailable http https
type running grown up cpu queue
""".split())

def clean(text):
    text = "" if pd.isna(text) else str(text)
    text = text.lower()

    text = re.sub(r"\b(?:inc|ic|team|vm|srv|host|id)[\s_-]*\d+[a-z0-9_-]*\b", " ", text)
    text = re.sub(r"https?://\S+|\S+@\S+", " ", text)

    text = (unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii"))

    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    tokens = []

    for word in text.split():
        if len(word) <= 2:
            continue

        if word in STOP:
            continue

        if STEMMER:
            word = STEMMER.stem(word)

        tokens.append(word)

    return " ".join(tokens)


def rank01(series, higher=True):
    rank = series.rank(method="min", ascending=not higher)
    return rank / rank.max()

print("Lendo Silver...")
df = pd.read_parquet(ARQUIVO_SILVER)

df = df[["Número", "Descrição resumida"]].copy()
df = df.rename(columns={"Número": "numero_incidente", "Descrição resumida": "descricao_original"})
df["descricao_original"] = (df["descricao_original"].fillna("").astype(str))
df["texto_limpo"] = (df["descricao_original"].apply(clean))

df = (df[df["texto_limpo"].str.len() > 0].reset_index(drop=True))
print(f"Incidentes válidos: {len(df):,}")

configs = []
vectorizers = [

    (
        "word_1_2",
        TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.98,
            sublinear_tf=True,
            max_features=30000
        )
    ),

    (
        "word_1_3",
        TfidfVectorizer(
            ngram_range=(1, 3),
            min_df=2,
            max_df=0.98,
            sublinear_tf=True,
            max_features=30000
        )
    ),

    (
        "char_3_5",
        TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=3,
            sublinear_tf=True,
            max_features=30000
        )
    )
]

for nome, vec in vectorizers:
    print(f"Testando {nome}")
    X = vec.fit_transform(df["texto_limpo"])

    for k in [4, 8, 10, 12]:
        print(f"  K={k}")
        model = MiniBatchKMeans(
            n_clusters=k,
            random_state=42,
            n_init=10,
            batch_size=2048)

        labels = model.fit_predict(X)
        sample_idx = (
            np.arange(len(df))
            if len(df) <= 10000
            else np.random.default_rng(42).choice(len(df), 10000, replace=False))

        X_sample = X[sample_idx]
        labels_sample = labels[sample_idx]

        svd = TruncatedSVD(n_components=100, random_state=42)
        X_eval = svd.fit_transform(X_sample)

        configs.append(
            {
                "config": nome,
                "k": k,
                "silhouette": silhouette_score(X_sample, labels_sample, metric="cosine"),
                "davies_bouldin": davies_bouldin_score(X_eval, labels_sample),
                "calinski_harabasz": calinski_harabasz_score(X_eval, labels_sample),
                "vectorizer": vec,
                "X": X,
                "labels": labels,
                "model": model })

# comparação
res = pd.DataFrame([
    {k: v
        for k, v in c.items()
        if k not in ["vectorizer", "X", "labels", "model"]} 
        for c in configs])

res["rank_sil"] = rank01(res["silhouette"], True)
res["rank_db"] = rank01(res["davies_bouldin"], False)

res["rank_ch"] = rank01(res["calinski_harabasz"], True)
res["score_geral"] = (res[["rank_sil", "rank_db", "rank_ch"]].mean(axis=1))

best_idx = res["score_geral"].idxmin()
best = configs[best_idx]

labels = best["labels"]
vectorizer = best["vectorizer"]
X = best["X"]
model = best["model"]

df["cluster"] = labels


# keywords dos clusters
terms = np.array(vectorizer.get_feature_names_out())

keywords_rows = []
summary_rows = []

for cluster in range(best["k"]):
    idx = np.where(labels == cluster)[0]
    centroid = model.cluster_centers_[cluster]
    top_idx = np.argsort(centroid)[::-1][:15]
    top_words = terms[top_idx]
    for palavra_idx in top_idx:

        keywords_rows.append({"cluster": cluster, "palavra": terms[palavra_idx], "score": centroid[palavra_idx] })

    summary_rows.append({
            "cluster": cluster,
            "quantidade_incidentes": len(idx),
            "percentual_dataset":
                len(idx) / len(df) * 100,

            "tema_cluster":
                " | ".join(top_words[:5])})


# descrição representativa
X_norm = normalize(X)
C_norm = normalize(model.cluster_centers_)

representantes = {}

for cluster in range(best["k"]):
    idx = np.where(labels == cluster)[0]
    sims = X_norm[idx].dot(C_norm[cluster])
    melhor = idx[int(np.argmax(sims))]
    representantes[cluster] = (df.iloc[melhor]["descricao_original"])


# dfs finais
cluster_summary = pd.DataFrame(summary_rows)
cluster_summary["descricao_representativa"] = cluster_summary["cluster"].map(representantes)
cluster_keywords = pd.DataFrame(keywords_rows)
incident_clusters = df[["numero_incidente", "descricao_original", "cluster"]]

best_metrics = pd.DataFrame([{
            "vectorizer": best["config"],
            "clusters": best["k"],
            "silhouette": res.loc[best_idx, "silhouette"],
            "davies_bouldin": res.loc[best_idx, "davies_bouldin"],
            "calinski_harabasz": res.loc[best_idx, "calinski_harabasz"],

            "score_geral": res.loc[best_idx, "score_geral"]}])

# exportações
incident_clusters.to_csv("outputs/incident_clusters.csv", index=False, encoding="utf-8-sig")
cluster_summary.to_csv("outputs/cluster_summary.csv", index=False, encoding="utf-8-sig")
cluster_keywords.to_csv("outputs/cluster_keywords.csv", index=False, encoding="utf-8-sig")

res.to_csv("outputs/clustering_model_comparison.csv", index=False, encoding="utf-8-sig")

best_metrics.to_csv("outputs/best_model_metrics.csv", index=False, encoding="utf-8-sig")


# salvar modelo
joblib.dump({"vectorizer": vectorizer, "model": model}, "artifacts/incident_clustering.joblib")

# resultados
print("melhor configuração encontrada")

print(f"Vectorizer: {best['config']}")
print(f"Número de Clusters: {best['k']}")

print("\nMÉTRICAS")
print(f"Silhouette Score: {res.loc[best_idx, 'silhouette']:.4f}")
print(f"Davies-Bouldin Index: {res.loc[best_idx, 'davies_bouldin']:.4f}")
print(f"Calinski-Harabasz Score: {res.loc[best_idx, 'calinski_harabasz']:.2f}")
print(f"Score Geral: {res.loc[best_idx, 'score_geral']:.6f}")

# upload pra gold

print("\nEnviando para Gold...")

client = storage.Client()

bucket = client.bucket(BUCKET_GOLD)

arquivos = [
    ("artifacts/incident_clustering.joblib", "modelos/incident_clustering.joblib"),
    ("outputs/incident_clusters.csv", "nlp/incident_clusters.csv"),
    ("outputs/cluster_summary.csv", "nlp/cluster_summary.csv"),
    ("outputs/cluster_keywords.csv", "nlp/cluster_keywords.csv"),
    ("outputs/best_model_metrics.csv", "nlp/best_model_metrics.csv")]

for local, destino in arquivos:
    blob = bucket.blob(destino)
    blob.upload_from_filename(local)
    print(f"Upload OK: {destino}")

print("PIPELINE NLP CONCLUÍDO")
