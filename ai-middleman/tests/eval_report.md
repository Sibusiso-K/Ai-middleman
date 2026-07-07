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
- Relevance rate: 7/14 (50.0%)

| Query | Top match | Result | Notes |
|---|---|---|---|
| I need a leveraged finance MD in London for a mid-market buyout | Dr. Jennifer Shelton DVM (Sterling Bridge Finance, London, UK) conf=0.95 | PASS |  |
| Find me a direct lending specialist in Dubai | Stacy Frazier (Northbridge Ventures, Dubai, UAE) conf=1.0 | PASS |  |
| Connect me with an M&A lawyer at a top firm in London | None | None | ERROR:  |
| Find a healthcare venture capital principal in Boston | None | None | ERROR:  |
| Need an energy infrastructure investor in Amsterdam | Brooke Smith (Copenhagen Infrastructure Partners, Amsterdam, Netherlands) conf=0.95 | PASS |  |
| Looking for an investment banking VP in Singapore | None | None | ERROR:  |
| Connect me with a private credit principal in Mumbai | Carrie Gillespie (Blackstone Credit, Mumbai, India) conf=0.7 | PASS |  |
| Find a corporate lawyer at Kirkland & Ellis | None | None | ERROR:  |
| Real estate investment chairman in Dubai | None | None | ERROR:  |
| Tech CTO in Zurich | Daniel Nichols (Pulse Health Tech, Zurich, Switzerland) conf=0.9 | PASS |  |
| Recruiting partner in Tel Aviv | None | None | ERROR:  |
| Someone in Johannesburg who does corporate law | None | None | ERROR:  |
| Any private equity partners in Dubai I should meet? | Colton Smith (Meridian Growth Partners, Dubai, UAE) conf=0.9 | PASS |  |
| Do you know any energy investors in Amsterdam? | David Tucker (NextEra Energy, Amsterdam, Netherlands) conf=0.85 | PASS |  |

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