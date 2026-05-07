Remaining Known Limitations                                                                                                                                                              
                                                                                                                                                                                        
R01 FAIL — "summarize this text for me" with no actual text: the model correctly explains the input is incomplete, but that explanation matches the echo detector pattern ("The user is 
asking for..."). This is a valid edge case in practice; degenerate inputs without text to process will always produce this behavior.                                                    
                                                                                                                                                                                        
N04 WARN — "What are the latest news about OpenAI?" routes to general (confidence=0.30, near threshold). The general handler still answers correctly from training data (q=0.81, terms  
1/1). No code path reaches web_search for news queries unless they're explicitly phrased as searches.                                                                                   
                                                                                                                                                                                        
N09 WARN — "What is spaCy?" now correctly routes to question_answering, and the LLM answers from training data (terms 3/3, q=0.65 — excellent answer). The WARN is a test expectation   
mismatch: we expected it to go through Wikipedia NER dispatch, but xx_ent_wiki_sm doesn't recognize "spaCy" as a named entity. The LLM answer is actually better than a Wikipedia       
                                                                                                                              

● Three distinct root causes, three different fix strategies. Here are concrete recommendations ordered by effort and value:
                                                                                          
  ---
  R01 — Empty summarization input                                                                                                                                                           
                                                                                                                                                                                            
  Root cause: the echo detector fires on a legitimate "I can't help with an empty input" explanation. The real bug is that the summarization handler lets degenerate inputs reach the LLM at
   all.                                                                                                                                                                                     
                                                            
  Recommendation: content guard in the summarization handler.                                                                                                                               
                                                            
  Before calling the LLM, strip the command words ("summarize", "tl;dr", "resume", etc.) and measure what's left. If the residual is too short to summarize, return early with a            
  deterministic message — no LLM, no echo risk.
                                                                                                                                                                                            
  # In app/handlers/summarization.py, at the top of handle()
  _COMMAND_RE = re.compile(                                                                                                                                                                 
      r"^\s*(summarize|tl;?dr|resume|resumo|faça um resumo|"                                                                                                                                
      r"me dá um resumo|pode resumir)[:\s]*",                                                                                                                                               
      re.IGNORECASE,                                                                                                                                                                        
  )                                                                                                                                                                                         
  _MIN_CONTENT_WORDS = 10                                                                                                                                                                   
                                                            
  def handle(user_input: str, llm: LLMClient) -> BaseModel:                                                                                                                                 
      content = _COMMAND_RE.sub("", user_input).strip()
      if len(content.split()) < _MIN_CONTENT_WORDS:                                                                                                                                         
          return FinalAnswer(answer="No text provided to summarize.")
      ...                                                                                                                                                                                   
                                                            
  This is ~6 lines, deterministic, zero LLM cost, and fixes R01 permanently regardless of what the model would say. It also fixes the broader case where a user sends just "summarize" with 
  nothing attached.                                         
                                                                                                                                                                                            
  ---                                                       
  N04 — "Latest news" queries route to general
                                                                                                                                                                                            
  Root cause: the TF-IDF sees "news" / "latest" as general-knowledge vocabulary, not search vocabulary. The function_calling training examples are all explicit ("search for", "look up")
  with no temporal phrasing.                                                                                                                                                                
                                                            
  Two complementary fixes, either alone is sufficient:                                                                                                                                      
                                                            
  Option A (router training data — 2 lines, high leverage):                                                                                                                                 
   
  Add temporal-search anchor phrases to _INTENT_EXAMPLES["function_calling"]:                                                                                                               
                                                            
  "function_calling": [                                                                                                                                                                     
      ...                                                                                                                                                                                   
      "latest news about",
      "recent news on",                                                                                                                                                                     
      "current news about",                                 
      "últimas notícias sobre",
      "notícias recentes",
      ...                                                                                                                                                                                   
  ]
                                                                                                                                                                                            
  One sentence in the TF-IDF vocabulary shifts the classifier's decision boundary. Low risk — temporal phrases are unambiguous signals for web retrieval.                                   
   
  Option B (pre-routing temporal gate — more robust):                                                                                                                                       
                                                            
  Before TF-IDF runs in route_task(), check for temporal signals and short-circuit to function_calling. Reuses _TEMPORAL_RE already defined in app/ner.py:                                  
                                                            
  # In router.py, before the ML/LLM routing                                                                                                                                                 
  from app.ner import is_temporal                                                                                                                                                           
  if is_temporal(user_input):                                                                                                                                                               
      return IntentClassification(                                                                                                                                                          
          intent="function_calling", confidence=0.9, reason="temporal"                                                                                                                      
      )                                                                                                                                                                                     
   
  This is deterministic and guarantees temporal queries always reach a tool. The tradeoff: it's slightly opinionated — "what happened yesterday to my code?" would route to function_calling
   even if the user just wants a conversational answer.     
                                                                                                                                                                                            
  Recommendation: Option A first. It's the smallest change and addresses the actual training gap. Add Option B only if A still leaves edge cases.                                           
   
  ---                                                                                                                                                                                       
  N09 — Niche entities not recognized by xx_ent_wiki_sm     
                                                                                                                                                                                            
  Root cause: xx_ent_wiki_sm was trained on Wikipedia text — it knows OpenAI, Rio de Janeiro, Linus Torvalds. It doesn't know spaCy, FastAPI, llama.cpp, or most library/tool names. These
  fall through to LLM-only QA, which works when the model has training data on the topic but silently fails for very niche or post-cutoff topics.                                           
                                                            
  Recommendation: proper-noun Wikipedia fallback in _fetch_context.                                                                                                                         
                                                            
  After NER returns empty, check whether the query contains a likely proper noun (capitalized token, camelCase, or mixed-case) and probe Wikipedia speculatively:                           
                                                            
  _PROPER_NOUN_RE = re.compile(                                                                                                                                                             
      r'\b([A-Z][a-z]{2,}|[a-z]+[A-Z][a-zA-Z]+)\b'  # Title-case or camelCase
  )                                                                                                                                                                                         
  _WHAT_IS_RE = re.compile(
      r'\b(what is|what are|what\'s|o que é|o que são)\b',                                                                                                                                  
      re.IGNORECASE,                                        
  )                                                                                                                                                                                         
                                                            
  def _fallback_entity(user_input: str) -> str | None:                                                                                                                                      
      """Extract a likely entity name when NER finds nothing."""
      if not _WHAT_IS_RE.search(user_input):                                                                                                                                                
          return None
      m = _PROPER_NOUN_RE.search(user_input)                                                                                                                                                
      return m.group(1) if m else None                      
                                                                                                                                                                                            
  Then in _fetch_context(), after the NER block returns empty:                                                                                                                              
   
  # Existing NER block                                                                                                                                                                      
  entities = ner.lookup_entities(user_input)                                                                                                                                                
  if entities:
      ...                                                                                                                                                                                   
                                                                                                                                                                                            
  # New: proper-noun fallback for niche entities NER misses
  candidate = _fallback_entity(user_input)                                                                                                                                                  
  if candidate:                                                                                                                                                                             
      wiki = wikipedia.run({"query": candidate})
      if "No Wikipedia article" not in wiki and "failed" not in wiki.lower():                                                                                                               
          trace.retrieval("wikipedia", candidate)                                                                                                                                           
          return context.compress(wiki, query=user_input, max_sentences=_MAX_CONTEXT_SENTENCES)
                                                                                                                                                                                            
  What this fixes: "What is spaCy?" → extracts "spaCy" (camelCase match) → Wikipedia lookup → grounded answer instead of LLM training data. Same for "What is FastAPI?", "What is           
  LangChain?", "What is Docker?" etc.                                                                                                                                                       
                                                                                                                                                                                            
  Tradeoff: a speculative Wikipedia call adds ~1-2s latency for these queries even when Wikipedia doesn't have the article. Mitigation: only trigger for queries that match _WHAT_IS_RE (a  
  narrow pattern) and cache misses are fast (Wikipedia returns a short "not found" string).
                                                                                                                                                                                            
  ---                                                       
  Summary
                                                                                                                                                                                            
  ┌─────────────────────┬─────────────────────────────────┬───────────┬────────────┐
  │     Limitation      │               Fix               │  Effort   │    Risk    │                                                                                                        
  ├─────────────────────┼─────────────────────────────────┼───────────┼────────────┤
  │ R01 empty summarize │ Content guard, early return     │ ~6 lines  │ Very low   │
  ├─────────────────────┼─────────────────────────────────┼───────────┼────────────┤
  │ N04 news routing    │ Add temporal examples to router │ ~3 lines  │ Low        │                                                                                                        
  ├─────────────────────┼─────────────────────────────────┼───────────┼────────────┤                                                                                                        
  │ N09 niche entities  │ Proper-noun Wikipedia fallback  │ ~15 lines │ Low-medium │                                                                                                        
  └─────────────────────┴─────────────────────────────────┴───────────┴────────────┘                                                                                                        
                                                            
  All three are purely additive — no existing paths are modified, just new gates inserted before the LLM is reached. The content guard (R01) is the highest-confidence fix. The temporal    
  router addition (N04) is the simplest. The proper-noun fallback (N09) has the most impact on real-world usage since niche tech entities are very common in developer queries.
                                                                                                                                                                                