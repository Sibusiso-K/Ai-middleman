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
- Relevance rate: 12/12 (100.0%)

| Query | Top match | Result | Notes |
|---|---|---|---|
| I need a leveraged finance MD in London for a mid-market buyout | Brenda Mays (Stealth (ex-Stripe), London, UK) conf=0.85 | PASS |  |
| Find me a direct lending specialist in Dubai | Amanda Ramirez (Sterling Bridge Finance, Dubai, UAE) conf=0.95 | PASS |  |
| Connect me with an M&A lawyer at a top firm in London | Bonnie Mercado (Linklaters, London, UK) conf=0.85 | PASS |  |
| Find a healthcare venture capital principal in Boston | Christopher Mcdonald (GV (Google Ventures), Boston, USA) conf=0.95 | PASS |  |
| Need an energy infrastructure investor in Amsterdam | Christian Garcia (Summit Peak Capital, Amsterdam, Netherlands) conf=0.85 | PASS |  |
| Looking for an investment banking VP in Singapore | Patricia Little (Northbridge Ventures, Singapore) conf=0.85 | PASS |  |
| Connect me with a private credit principal in Mumbai | Angela Castillo (Summit Peak Capital, Mumbai) conf=1.0 | PASS |  |
| Find a corporate lawyer at Kirkland & Ellis | Lauren Boyd (Kirkland & Ellis, Frankfurt, Germany) conf=0.9 | PASS |  |
| Real estate investment chairman in Dubai | John Montoya (Patrizia, Dubai, UAE) conf=0.85 | PASS |  |
| Tech CTO in Zurich | Jennifer Rodriguez (Macquarie Green Investment, Zurich, Switzerland) conf=0.85 | PASS |  |
| Recruiting partner in Tel Aviv | Mr. Lawrence Edwards (Databricks, Tel Aviv, Israel) conf=1.0 | PASS |  |
| Someone in Johannesburg who does corporate law | Dr. Melissa Young (PwC Deals, São Paulo, Brazil) conf=0.35 | PASS |  |