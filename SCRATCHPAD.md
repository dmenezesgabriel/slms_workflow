- Replace hardcoded string blacklists with algorithmic/ML-based approaches. The modules have too many brittle heuristics
- Analytics Engineer Agent: Acts as an AI assistant that can create calculated fields, build visualizations, and answer analytical questions.
- Data Storytelling & Summaries: Automatically generates narratives that describe key patterns, outliers, and trends.
- Semantic Modeling Support: AI assists in mapping data and creating consistent definitions (e.g., defining "Profit" vs. "Revenue").
- Context Retention: The Agent remembers previous questions to support follow-up questions, similar to chat interfaces.
- Transforms complex datasets into clear, narrative insights by automatically generating written explanations of your data

- Tool calling:

```py
import duckdb
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, ToolMessage

con = duckdb.connect(database="ducks.duckdb")
schema = con.execute(f"DESCRIBE ducks").fetchall()
schema_str = schema.to_string(index=False)

@tool
def query(query: str) -> str:
    """Queries the database for information and returns the result.

    Args:
        query: The query to run against the database.
    """
    return str(con.execute(query).fetchone()[0])

llm = ChatOllama(model="qwen2.5-coder").bind_tools([query])

try:
    while True:
        user_query = input(">>> ")
        messages = [HumanMessage(f"You are provided You are given a DuckDB schema for table 'ducks':\n\n{schema_str}\n\n.\n\nAnswer the user query: '{user_query}' in a single sentence.")]
        ai_msg = llm.invoke(messages)
        messages.append(ai_msg)
```

- RAG:

```py
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.vector_stores.duckdb import DuckDBVectorStore
from llama_index.core import StorageContext
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

# models
Settings.embed_model = OllamaEmbedding(model_name="all-minilm")
Settings.llm = Ollama(model="gemma2:2b", temperature=0, request_timeout=360.0)

# load documents into a vector store (DuckDB)
documents = SimpleDirectoryReader(input_files=["facts.txt"]).load_data(show_progress=True)
splitter = TokenTextSplitter(separator="\n", chunk_size=64, chunk_overlap=0)
vector_store = DuckDBVectorStore()
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex(
    splitter.get_nodes_from_documents(documents),
    storage_context=storage_context,
    show_progress=True,
)
query_engine = index.as_query_engine()

try:
    while True:
        user_query = input(">>> ")
        response = query_engine.query(user_query)
        print(response)
except KeyboardInterrupt:
    exit()
```

- prompts semantically sharper.

- RAG: https://huggingface.co/LiquidAI/LFM2-1.2B-RAG-GGUF
- GENERAL: https://huggingface.co/ibm-granite/granite-4.0-h-1b-GGUF
- CODE: https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF
- Internet Search: https://huggingface.co/ibm-granite/granite-4.0-h-micro-GGUF


- https://www.youtube.com/watch?v=wJEP4CuR6a4
- LLM Studio
- OpenWebUI
- https://gist.github.com/chenhunghan/26b36d0e30ed8f4b6dbce699bf085423
- https://arxiv.org/abs/2310.03714
- https://dspy.ai/api/optimizers/MIPROv2
- https://arxiv.org/abs/2211.01910
- https://arxiv.org/abs/2305.03495
- https://arxiv.org/abs/2309.08532
- https://github.com/aurelio-labs/semantic-router
--- 

A good system for “prompt engineering semantic focus meta-analysis” could look like this:

1. Parse prompt/skill into semantic sections
   - purpose
   - scope
   - workflow
   - constraints
   - anti-patterns
   - output contract

2. Extract key semantic claims
   - verbs: implement, test, validate, refactor
   - quality attributes: cohesive, modular, deterministic, accessible
   - constraints: no overengineering, no workaround, no broad rewrites

3. Compute embeddings per sentence/section
   - detect redundancy by high cosine similarity
   - detect weak coverage by comparing against a target concept taxonomy
   - detect off-topic text by distance from the skill objective

4. Score the prompt
   - semantic coverage
   - instruction specificity
   - ambiguity risk
   - redundancy
   - token efficiency
   - behavioral testability
   - constraint preservation

5. Generate candidate rewrites
   - APE-style: generate prompt variants
   - ProTeGi/TextGrad-style: critique failures and rewrite
   - EvoPrompt-style: mutate/crossover strong variants
   - DSPy-style: optimize against examples and a metric

6. Evaluate candidates
   - semantic similarity to required concepts
   - lower similarity to forbidden concepts / anti-patterns
   - output quality on benchmark tasks
   - compactness
   - consistency across multiple LLMs

7. Select best prompt
   - Pareto frontier: precision vs brevity vs coverage
   - not just highest similarity
The most useful mathematical concepts

For your case, I would focus on these:

Concept	Use
Embedding vectors	Represent prompt sections semantically
Cosine similarity	Detect semantic overlap/redundancy
Semantic textual similarity	Compare candidate prompt vs target intent
Clustering	Group repeated or related instructions
Centroid distance	Measure whether a prompt stays focused on its main objective
Information density	Estimate meaning per token
Multi-objective optimization	Balance precision, brevity, coverage, and non-redundancy
Beam search	Keep top prompt candidates across rewrite rounds
Bandit selection	Allocate more evaluation budget to promising candidates
Bayesian optimization	Optimize prompt/demo combinations efficiently
Evolutionary search	Explore diverse prompt structures
Recommended implementation stack

For a practical prototype:

Python
DSPy
sentence-transformers
scikit-learn
numpy
pandas
bertscore
rapidfuzz
umap-learn or hdbscan, optional

For LLM optimization:

DSPy MIPROv2
TextGrad
custom APE loop
custom ProTeGi-style critique loop

For semantic scoring:

sentence-transformers/all-MiniLM-L6-v2
BAAI/bge-small-en-v1.5
intfloat/e5-small-v2
BERTScore
cosine similarity
A compact metric design

For your “skill prompt” meta-analysis, I would define a score like this:

final_score =
  0.30 * behavioral_coverage
+ 0.20 * semantic_precision
+ 0.15 * constraint_preservation
+ 0.15 * testability
+ 0.10 * token_efficiency
- 0.10 * redundancy
- 0.10 * ambiguity

Where:

behavioral_coverage = similarity(skill, target_behavior_taxonomy)
semantic_precision = similarity(each sentence, core objective)
redundancy = average pairwise sentence similarity above threshold
ambiguity = count of vague terms without operational definition
token_efficiency = useful semantic units / token count
constraint_preservation = similarity(candidate_constraints, required_constraints)
Most relevant papers to start with

Start in this order:

DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines — best architecture model.
Large Language Models Are Human-Level Prompt Engineers — APE / prompt-as-program search.
Automatic Prompt Optimization with “Gradient Descent” and Beam Search — ProTeGi / textual gradients.
TextGrad: Automatic “Differentiation” via Text — optimization of text variables in computation graphs.
Connecting Large Language Models with Evolutionary Algorithms Yields Powerful Prompt Optimizers — evolutionary prompt search.
BERTScore: Evaluating Text Generation with BERT — semantic evaluation beyond exact matching.
SEMSCORE — simple semantic similarity evaluation for generated responses.
A Systematic Survey of Automatic Prompt Optimization — broader taxonomy of APO methods.

The strongest practical architecture would be: DSPy-style prompt-as-program + ProTeGi/TextGrad-style critique loop + embedding/BERTScore semantic metrics + multi-objective ranking.