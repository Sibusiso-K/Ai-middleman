# AI Middleman — Evaluation Report

## Intent classification
- Accuracy: 75.0%
- Precision: 66.7%
- Recall: 100.0%
- F1: 80.0%
- Confusion: TP=10 FP=5 TN=5 FN=0 (errors=0)

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
| False | True | FAIL | Movie night this weekend still on? |
| False | True | FAIL | Appreciate you covering for me at the meeting |
| False | True | FAIL | Ring me later, I'm swamped rn |
| False | False | PASS | Crazy how the markets are behaving lately huh |
| False | True | FAIL | Confirmed |
| False | False | PASS | haha no way, that's wild |
| False | True | FAIL | Congrats on the promotion!! |
| False | False | PASS | Watched the match last night, wild finish |
| False | False | PASS | Running behind, be there in 10 |

## Matching relevance
- Relevance rate: 10/15 (66.7%)

| Query | Top match | Result | Notes |
|---|---|---|---|
| I need a leveraged finance MD in London for a mid-market buyout | None | None | ERROR:  |
| Find me a direct lending specialist in Dubai | Steven Cook (Meridian Growth Partners, Dubai, UAE) conf=0.9 | PASS |  |
| Connect me with an M&A lawyer at a top firm in London | Bonnie Mercado (Linklaters, London, UK) conf=0.9 | PASS |  |
| Find a healthcare venture capital principal in Boston | Samuel Contreras (Catalio Capital, Boston, USA) conf=0.9 | PASS |  |
| Need an energy infrastructure investor in Amsterdam | None | None | ERROR:  |
| Looking for an investment banking VP in Singapore | Donald Decker (JP Morgan, Singapore) conf=0.5 | PASS |  |
| Connect me with a private credit principal in Mumbai | Andrea Powell (KKR Credit, Mumbai, India) conf=0.85 | PASS |  |
| Find a corporate lawyer at Kirkland & Ellis | Lauren Boyd (Kirkland & Ellis, Frankfurt, Germany) conf=0.9 | PASS |  |
| Real estate investment chairman in Dubai | Mary Whitaker (LaSalle Investment, Dubai, UAE) conf=0.9 | PASS |  |
| Tech CTO in Zurich | None | None | ERROR:  |
| Recruiting partner in Tel Aviv | Kayla Jordan (Odgers Berndtson, Tel Aviv, Israel) conf=0.9 | PASS |  |
| Someone in Johannesburg who does corporate law | Jacqueline Lopez (Latham & Watkins, Mumbai, India) conf=0.5 | FAIL | expected a low-confidence/no match (this location isn't in the dataset) but got a confident hit — possible hallucination |
| Any private equity partners in Dubai I should meet? | None | None | ERROR:  |
| Do you know any energy investors in Amsterdam? | Steven Gross (Vitol, Amsterdam, Netherlands) conf=0.85 | PASS |  |
| Do you know anyone from JPMorgan in a senior position? | Michael Sanchez (JP Morgan, Los Angeles, USA) conf=0.9 | PASS |  |

## Follow-up selection
- Selection accuracy: 20/20 (100.0%)

| Follow-up | Expected | Got | Result |
|---|---|---|---|
| okay connect me with John | ['John Hall'] | ['John Hall'] | PASS |
| connect me with John and Sally | ['John Hall', 'Sally Meyer'] | ['John Hall', 'Sally Meyer'] | PASS |
| Sally should be perfect, shot me their details | ['Sally Meyer'] | ['Sally Meyer'] | PASS |
| the second one works | ['Sally Meyer'] | ['Sally Meyer'] | PASS |
| both of them please | ['David Cohen', 'John Hall', 'Sally Meyer'] | ['David Cohen', 'John Hall', 'Sally Meyer'] | PASS |
| both of them | ['David Cohen', 'John Hall', 'Sally Meyer'] | ['David Cohen', 'John Hall', 'Sally Meyer'] | PASS |
| connect me with all three | ['David Cohen', 'John Hall', 'Sally Meyer'] | ['David Cohen', 'John Hall', 'Sally Meyer'] | PASS |
| connect me with them | ['David Cohen', 'John Hall', 'Sally Meyer'] | ['David Cohen', 'John Hall', 'Sally Meyer'] | PASS |
| sure connect me with dem | ['David Cohen', 'John Hall', 'Sally Meyer'] | ['David Cohen', 'John Hall', 'Sally Meyer'] | PASS |
| what about them? | (none) | (none) | PASS |
| send me David and John's details | ['David Cohen', 'John Hall'] | ['David Cohen', 'John Hall'] | PASS |
| great, go with the first one | ['John Hall'] | ['John Hall'] | PASS |
| John is too junior, anyone else? | (none) | (none) | PASS |
| what does David do again? | (none) | (none) | PASS |
| actually I need a lawyer in Dubai instead | (none) | (none) | PASS |
| yeah | (none) | (none) | PASS |
| acount with them | ['David Cohen', 'John Hall', 'Sally Meyer'] | ['David Cohen', 'John Hall', 'Sally Meyer'] | PASS |
| connect me with all of em | ['David Cohen', 'John Hall', 'Sally Meyer'] | ['David Cohen', 'John Hall', 'Sally Meyer'] | PASS |
| okay acount with them please | ['David Cohen', 'John Hall', 'Sally Meyer'] | ['David Cohen', 'John Hall', 'Sally Meyer'] | PASS |
| are they any good? | (none) | (none) | PASS |

## Language guard
- Guard accuracy: 8/8 (100.0%)

| Message | Expected (is Nguni) | Got | Result |
|---|---|---|---|
| Ngifuna ummuntu kwiEnergy sector | True | True | PASS |
| Ngidinga ummeli waseLondon wamashishini | True | True | PASS |
| Sawubona Sam | True | True | PASS |
| ek soek William williams | False | False | PASS |
| Ken jy iemand wat n korporatiewe prokureur is in Londen? | False | False | PASS |
| Any solid corporate lawyers you know in Frankfurt? | False | False | PASS |
| This is amazing, thank you | False | False | PASS |
| connect me with all of them | False | False | PASS |