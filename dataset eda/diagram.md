digraph Pipeline {
  rankdir=LR;
  node [shape=roundrect, style=filled, fontsize=10];

  A [label="Data Ingestion & Preprocessing\n• Clean/Impute/Dedupe\n• Outliers\n• Monthly Aggregation", fillcolor="#eef7ff", color="#4a90e2"];

  subgraph cluster_backend {
    label="FastAPI Backend";
    color="#7b61ff";
    B1 [label="Intent Parser\n(rule + NLP)", fillcolor="#f5f0ff", color="#7b61ff"];
    B2 [label="Pandas Runner\n(Top-N, MAT, YTD, YoY)", fillcolor="#f5f0ff", color="#7b61ff"];
    B3 [label="Forecasting\nARIMA/SARIMA/Prophet", fillcolor="#f5f0ff", color="#7b61ff"];
    B1 -> B2 -> B3;
  }

  subgraph cluster_insights {
    label="Insights Engine";
    color="#ffb200";
    C1 [label="LLM / Templates", fillcolor="#fff8e6", color="#ffb200"];
    C2 [label="Stat Tests\n(t-test, ANOVA, KW)", fillcolor="#fff8e6", color="#ffb200"];
    C3 [label="Forecast Insights", fillcolor="#fff8e6", color="#ffb200"];
  }

  subgraph cluster_ui {
    label="Streamlit Frontend";
    color="#1dbf84";
    D1 [label="Upload & Settings", fillcolor="#e9fff3", color="#1dbf84"];
    D2 [label="Q&A Input", fillcolor="#e9fff3", color="#1dbf84"];
    D3 [label="Charts\n(Line/Bar/Pie/Pareto)", fillcolor="#e9fff3", color="#1dbf84"];
    D4 [label="Key Insights Panel", fillcolor="#e9fff3", color="#1dbf84"];
  }

  subgraph cluster_devops {
    label="Deployment & MLOps";
    color="#ff6b81";
    E1 [label="Docker", fillcolor="#fdeef0", color="#ff6b81"];
    E2 [label="CI/CD\nGitHub Actions", fillcolor="#fdeef0", color="#ff6b81"];
    E3 [label="Cloud\nAWS/Azure/GCP", fillcolor="#fdeef0", color="#ff6b81"];
    E1 -> E2 -> E3;
  }

  A -> B1;
  B2 -> D3;
  B3 -> C3;
  B2 -> C2;
  B1 -> C1;
  C1 -> D4;
  C2 -> D4;
  C3 -> D4;
  D1 -> A;
  D2 -> B1;
}