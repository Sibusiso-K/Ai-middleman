export const SECTORS = [
  { name: "Finance", color: "oklch(0.65 0.15 268)" },
  { name: "Tech", color: "oklch(0.7 0.15 200)" },
  { name: "Legal", color: "oklch(0.65 0.13 320)" },
  { name: "Real Estate", color: "oklch(0.7 0.14 60)" },
  { name: "Healthcare", color: "oklch(0.68 0.14 160)" },
  { name: "Energy", color: "oklch(0.72 0.15 90)" },
  { name: "Recruiting", color: "oklch(0.65 0.12 20)" },
];

export const LOCATIONS = [
  "London", "Tel Aviv", "Dubai", "São Paulo", "Singapore",
  "New York", "Zurich", "Hong Kong", "Johannesburg", "Paris",
];

const FIRST = ["Sarah", "David", "Rachel", "Michael", "Ayelet", "Jonas", "Priya", "Marcus", "Elena", "Thomas", "Noa", "Adrien", "Ines", "Yuki", "Omar", "Beatriz"];
const LAST = ["Cohen", "Levi", "Sharma", "Weiss", "Barros", "Nakamura", "Al-Farsi", "Mendes", "Fischer", "O'Brien", "Kaplan", "Petit", "Rossi", "Chen"];
const TITLES = [
  "VP Leveraged Finance", "Managing Director", "Partner", "Senior Associate",
  "Head of M&A", "Portfolio Manager", "Corporate Lawyer", "General Counsel",
  "CTO", "VP Engineering", "CFO", "Head of Real Estate",
  "Investment Director", "Founder", "Talent Partner",
];
const COMPANIES = [
  "Blackstone", "Goldman Sachs", "Herzog Fox", "Meridian Capital", "Apollo",
  "Sequoia", "Latham & Watkins", "JLL", "Bridgepoint", "Ares", "Kirkland & Ellis",
  "Barclays", "Insight Partners", "Wix", "Check Point",
];

function seeded(i: number) {
  let x = Math.sin(i * 9301 + 49297) * 233280;
  return x - Math.floor(x);
}

export type Contact = {
  id: string;
  name: string;
  initials: string;
  title: string;
  company: string;
  sector: string;
  location: string;
  seniority: string;
  strength: number;
  vip: boolean;
  matchedIn: number;
};

export const CONTACTS: Contact[] = Array.from({ length: 48 }, (_, i) => {
  const first = FIRST[Math.floor(seeded(i) * FIRST.length)];
  const last = LAST[Math.floor(seeded(i + 100) * LAST.length)];
  const title = TITLES[Math.floor(seeded(i + 200) * TITLES.length)];
  const company = COMPANIES[Math.floor(seeded(i + 300) * COMPANIES.length)];
  const sector = SECTORS[Math.floor(seeded(i + 400) * SECTORS.length)].name;
  const loc = LOCATIONS[Math.floor(seeded(i + 500) * LOCATIONS.length)];
  const strength = Math.max(1, Math.round(seeded(i + 600) * 5));
  return {
    id: `c-${i + 1}`,
    name: `${first} ${last}`,
    initials: `${first[0]}${last[0]}`,
    title,
    company,
    sector,
    location: loc,
    seniority: ["Junior", "Mid", "Senior", "Executive"][Math.floor(seeded(i + 700) * 4)],
    strength,
    vip: seeded(i + 800) > 0.78,
    matchedIn: Math.floor(seeded(i + 900) * 12),
  };
});

export const SECTOR_STATS = SECTORS.map((s) => ({
  name: s.name,
  color: s.color,
  value: Math.round(3000 + seeded(s.name.length * 7) * 12000),
}));

export const LOCATION_STATS = LOCATIONS.map((l, i) => ({
  name: l,
  value: Math.round(1200 + seeded(i + 11) * 6500),
})).sort((a, b) => b.value - a.value);

export const TOP_SKILLS = [
  { name: "Leveraged Finance", count: 142 },
  { name: "M&A Advisory", count: 128 },
  { name: "Unitranche", count: 96 },
  { name: "Series B Founders", count: 84 },
  { name: "Real Estate Debt", count: 71 },
  { name: "Corporate Litigation", count: 63 },
  { name: "AI / ML Engineering", count: 58 },
  { name: "Energy Transition", count: 44 },
];

export type Thread = {
  id: string;
  contact: string;
  phone: string;
  preview: string;
  time: string;
  pending: number;
  status: "pending" | "answered";
  messages: { from: "them" | "us"; text: string; time: string }[];
  suggested?: { confidence: number; match: string; role: string; company: string; reply: string };
};

export const THREADS: Thread[] = [
  {
    id: "t1",
    contact: "James Whitfield",
    phone: "+44 7700 900412",
    preview: "Need a VP Leveraged Finance in London, unitranche focus…",
    time: "2m",
    pending: 1,
    status: "pending",
    messages: [
      { from: "them", text: "Hey Sam — I need a VP of Leveraged Finance in London who specialises in unitranche deals. Ideally warm intro.", time: "10:42" },
      { from: "us", text: "On it — pulling matches now.", time: "10:43" },
    ],
    suggested: {
      confidence: 94,
      match: "Rachel Weiss",
      role: "VP Leveraged Finance",
      company: "Ares",
      reply: "Best match is Rachel Weiss (VP Leveraged Finance @ Ares, London). Strong unitranche track record — happy to intro?",
    },
  },
  {
    id: "t2",
    contact: "Ayelet Barros",
    phone: "+972 54 123 8890",
    preview: "Looking for a corporate lawyer in Joburg…",
    time: "18m",
    pending: 1,
    status: "pending",
    messages: [
      { from: "them", text: "Need a corporate lawyer in Johannesburg for a cross-border deal. Any VIPs?", time: "10:25" },
    ],
    suggested: {
      confidence: 81,
      match: "David Cohen",
      role: "Partner",
      company: "Herzog Fox",
      reply: "David Cohen (Partner @ Herzog Fox) has JHB desk experience. Want me to introduce?",
    },
  },
  {
    id: "t3",
    contact: "Marcus Fischer",
    phone: "+41 79 555 2231",
    preview: "Thanks — connect me with her next week.",
    time: "1h",
    pending: 0,
    status: "answered",
    messages: [
      { from: "them", text: "Need a portfolio manager focused on European credit.", time: "09:10" },
      { from: "us", text: "Elena Rossi (Portfolio Manager @ Apollo, Zurich). Introducing now.", time: "09:12" },
      { from: "them", text: "Thanks — connect me with her next week.", time: "09:15" },
    ],
  },
  {
    id: "t4",
    contact: "Priya Sharma",
    phone: "+65 8123 4567",
    preview: "Any founders raising Series B in fintech?",
    time: "3h",
    pending: 1,
    status: "pending",
    messages: [
      { from: "them", text: "Any Series B fintech founders in APAC I should meet?", time: "07:40" },
    ],
    suggested: {
      confidence: 62,
      match: "Yuki Nakamura",
      role: "Founder",
      company: "Sequoia-backed",
      reply: "Yuki Nakamura (Founder, Singapore fintech, closing Series B). Lower confidence — worth double-checking.",
    },
  },
];

export const ACTIVITY = [
  { icon: "match", text: "AI matched Rachel Weiss for James Whitfield's request", time: "2m ago" },
  { icon: "draft", text: "Draft reply pending approval — Ayelet Barros thread", time: "18m ago" },
  { icon: "sent", text: "Sam approved intro to Elena Rossi", time: "1h ago" },
  { icon: "contact", text: "12 new contacts imported from LinkedIn export", time: "3h ago" },
  { icon: "match", text: "AI matched David Cohen for a JHB legal request", time: "5h ago" },
];

export const AUDIT_LOG = [
  { who: "Sam", action: "Approved", subject: "Reply to James Whitfield", time: "10:44 · today" },
  { who: "Sam", action: "Edited & sent", subject: "Reply to Marcus Fischer", time: "09:12 · today" },
  { who: "Sam", action: "Rejected", subject: "Suggested match for Priya Sharma", time: "yesterday" },
  { who: "Sam", action: "Approved", subject: "Reply to Jonas Fischer", time: "yesterday" },
];

export const EXAMPLE_QUERIES = [
  "VP Leveraged Finance in London, unitranche focus",
  "Corporate lawyer in Johannesburg, cross-border M&A",
  "Series B fintech founder in Singapore",
  "Real estate debt investor in Dubai",
];

export const SCATTER_DATA = CONTACTS.map((c) => ({
  x: c.strength,
  y: c.matchedIn,
  sector: c.sector,
}));
