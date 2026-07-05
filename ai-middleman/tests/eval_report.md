# AI Middleman — Evaluation Report

## Intent classification
- Accuracy: 100.0%
- Precision: 100.0%
- Recall: 100.0%
- F1: 100.0%
- Confusion: TP=10 FP=0 TN=10 FN=0 (errors=0)

| Expected | Actual | Result | Message |
|---|---|---|---|
| True | True | PASS | Any solid corporate lawyers you know in Frankfurt? |
| True | True | PASS | Who's good for private equity out in New York? |
| True | True | PASS | Need someone senior in real estate finance based in Dubai |
| True | True | PASS | hey can u connect me w a healthcare vc in boston |
| True | True | PASS | any leveraged finance ppl in london u kno |
| True | True | PASS | Trying to raise a Series A - know good fintech investors? |
| True | True | PASS | My company needs an M&A advisor, any names? |
| True | True | PASS | Who should I talk to about structured credit in Hong Kong? |
| True | True | PASS | Hiring a CFO soon, anyone spring to mind? |
| True | True | PASS | Could you put me in touch with someone at Kirkland & Ellis? |
| False | False | PASS | Yo what's good |
| False | False | PASS | Movie night this weekend still on? |
| False | False | PASS | Appreciate you covering for me at the meeting |
| False | False | PASS | Ring me later, I'm swamped rn |
| False | False | PASS | Crazy how the markets are behaving lately huh |
| False | False | PASS | Confirmed |
| False | False | PASS | haha no way, that's wild |
| False | False | PASS | Congrats on the promotion!! |
| False | False | PASS | Watched the match last night, wild finish |
| False | False | PASS | Running behind, be there in 10 |

## Matching relevance
- Relevance rate: 10/12 (83.3%)

| Query | Top match | Result | Notes |
|---|---|---|---|
| I need a leveraged finance MD in London for a mid-market buyout | Ryan Russell (Apollo Global, London, UK) conf=0.95 | PASS |  |
| Find me a direct lending specialist in Dubai | Tonya Sharp (Goldman Sachs, Dubai, UAE) conf=0.95 | PASS |  |
| Connect me with an M&A lawyer at a top firm in London | None | None | ERROR:  |
| Find a healthcare venture capital principal in Boston | Kara Davis (Sofinnova Partners, Boston, USA) conf=0.95 | PASS |  |
| Need an energy infrastructure investor in Amsterdam | John Mcgee (Copenhagen Infrastructure Partners, Amsterdam, Netherlands) conf=0.95 | PASS |  |
| Looking for an investment banking VP in Singapore | Joseph Cabrera (Heidrick & Struggles, Singapore) conf=0.85 | PASS |  |
| Connect me with a private credit principal in Mumbai | Sheila Thompson (Orsted, Mumbai, India) conf=0.85 | PASS |  |
| Find a corporate lawyer at Kirkland & Ellis | Travis Dixon (Kirkland & Ellis, Chicago, USA) conf=0.95 | PASS |  |
| Real estate investment chairman in Dubai | James Bailey (Crown Estate Partners, Dubai, UAE) conf=0.95 | PASS |  |
| Tech CTO in Zurich | Jason Trujillo (Forge Analytics, Zurich, Switzerland) conf=0.95 | PASS |  |
| Recruiting partner in Tel Aviv | John Brown (Forge Analytics, Tel Aviv, Israel) conf=0.95 | PASS |  |
| Someone in Johannesburg who does corporate law | Suzanne Garcia (BCG, Paris, France) conf=0.5 | FAIL | expected a low-confidence/no match (this location isn't in the dataset) but got a confident hit — possible hallucination |

## Follow-up selection
- Selection accuracy: 12/12 (100.0%)

| Follow-up | Expected | Got | Result |
|---|---|---|---|
| okay connect me with John | ['John Hall'] | ['John Hall'] | PASS |
| connect me with John and Sally | ['John Hall', 'Sally Meyer'] | ['John Hall', 'Sally Meyer'] | PASS |
| Sally should be perfect, shot me their details | ['Sally Meyer'] | ['Sally Meyer'] | PASS |
| the second one works | ['Sally Meyer'] | ['Sally Meyer'] | PASS |
| both of them please | ['David Cohen', 'John Hall', 'Sally Meyer'] | ['David Cohen', 'John Hall', 'Sally Meyer'] | PASS |
| connect me with all three | ['David Cohen', 'John Hall', 'Sally Meyer'] | ['David Cohen', 'John Hall', 'Sally Meyer'] | PASS |
| send me David and John's details | ['David Cohen', 'John Hall'] | ['David Cohen', 'John Hall'] | PASS |
| great, go with the first one | ['John Hall'] | ['John Hall'] | PASS |
| John is too junior, anyone else? | (none) | (none) | PASS |
| what does David do again? | (none) | (none) | PASS |
| actually I need a lawyer in Dubai instead | (none) | (none) | PASS |
| yeah | (none) | (none) | PASS |