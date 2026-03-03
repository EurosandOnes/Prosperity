/**
 * mockFunds.js — Hardcoded fund data for development/preview.
 *
 * lat/lng sourced from verified office addresses (Companies House, fund websites).
 * Neighborhood names match the actual office location.
 *
 * Position on map is computed dynamically via Mercator projection in CityMap.jsx.
 */

const MOCK_FUNDS = [
  // ── Soho cluster ──
  { id:"index",name:"Index Ventures",initials:"IX",focus:"Multi-stage",neighborhood:"Soho",
    lat:51.5127,lng:-0.1371, // 5-8 Lower John Street, W1F 9DY
    aum:"€3.2B",founded:1996,website:"https://www.indexventures.com",hiring:true,roles:[
    {title:"Principal",freshness:"HOT",source:"linkedin",url:"#",description:"Investment role focused on European growth-stage enterprise software. 4-6 years experience in VC, PE, or operating roles.",posted:"3 days ago"},
    {title:"Analyst",freshness:"WARM",source:"website",url:"#",description:"Two-year analyst programme supporting deal sourcing, due diligence, and portfolio analytics.",posted:"2 weeks ago"},
  ]},
  { id:"felix",name:"Felix Capital",initials:"FX",focus:"Consumer",neighborhood:"Soho",
    lat:51.5130,lng:-0.1380, // 27 Beak Street, W1F 9RU
    aum:"€1B",founded:2015,website:"https://www.felixcap.com",hiring:true,roles:[
    {title:"Associate",freshness:"HOT",source:"website",url:"#",description:"Consumer technology investment role. Digital brands, creator economy, and consumer fintech. 2-4 years experience.",posted:"4 days ago"},
  ]},
  { id:"dawn",name:"Dawn Capital",initials:"DC",focus:"B2B / Enterprise",neighborhood:"Soho",
    lat:51.5142,lng:-0.1310, // Ilona Rose House, Manette Street, W1D 4AL
    aum:"€1B",founded:2007,website:"https://dawncapital.com",hiring:true,roles:[
    {title:"Analyst",freshness:"HOT",source:"linkedin",url:"#",description:"B2B software focused analyst role. Financial modelling, competitive analysis, and deal support across European enterprise SaaS.",posted:"1 day ago"},
  ]},
  { id:"eqt",name:"EQT Ventures",initials:"EQ",focus:"Growth",neighborhood:"Soho",
    lat:51.5140,lng:-0.1368, // 30 Broadwick Street, W1F 8JB
    aum:"€3B",founded:2016,website:"https://eqtventures.com",hiring:true,roles:[
    {title:"Investment Associate",freshness:"WARM",source:"website",url:"#",description:"Growth equity role supporting European expansion-stage technology companies.",posted:"18 days ago"},
  ]},
  { id:"mosaic",name:"Mosaic Ventures",initials:"MV",focus:"Deep Tech",neighborhood:"Soho",
    lat:51.5125,lng:-0.1373, // 2-3 Golden Square, W1F
    aum:"€400M",founded:2014,website:"https://www.mosaicventures.com",hiring:true,roles:[
    {title:"Research Associate",freshness:"HOT",source:"website",url:"#",description:"Deep technology research and investment support. PhD or strong technical background preferred.",posted:"6 days ago"},
  ]},

  // ── St James's ──
  { id:"accel",name:"Accel",initials:"AC",focus:"Multi-stage",neighborhood:"St James's",
    lat:51.5068,lng:-0.1395, // 16 St James's Street, SW1A 1ER
    aum:"$3B",founded:1983,website:"https://www.accel.com",hiring:false,roles:[]},

  // ── Fitzrovia cluster ──
  { id:"atomico",name:"Atomico",initials:"AT",focus:"Growth",neighborhood:"Fitzrovia",
    lat:51.5178,lng:-0.1352, // 29 Rathbone Street, W1T 1NJ
    aum:"€4.5B",founded:2006,website:"https://atomico.com",hiring:true,roles:[
    {title:"Investment Associate",freshness:"HOT",source:"linkedin",url:"#",description:"Supporting deal execution across European growth equity. Strong modelling and sector research required.",posted:"5 days ago"},
  ]},
  { id:"northzone",name:"Northzone",initials:"NZ",focus:"Early Stage",neighborhood:"Fitzrovia",
    lat:51.5188,lng:-0.1408, // 20-22 Great Titchfield Street, W1W 8BE
    aum:"€2.5B",founded:1996,website:"https://northzone.com",hiring:true,roles:[
    {title:"Investment Analyst",freshness:"HOT",source:"linkedin",url:"#",description:"Sourcing and evaluating early-stage European technology companies. Modelling, market mapping, and founder engagement.",posted:"2 days ago"},
    {title:"Platform Associate",freshness:"WARM",source:"website",url:"#",description:"Supporting portfolio companies across talent, GTM, and operational scaling.",posted:"3 weeks ago"},
  ]},
  { id:"seedcamp",name:"Seedcamp",initials:"SC",focus:"Pre-seed / Seed",neighborhood:"Fitzrovia",
    lat:51.5175,lng:-0.1410, // 12 Little Portland Street, W1W 8BJ
    aum:"€400M",founded:2007,website:"https://seedcamp.com",hiring:true,roles:[
    {title:"Venture Fellow",freshness:"WARM",source:"linkedin",url:"#",description:"6-month fellowship for aspiring investors. Deal flow, portfolio support, and fund operations exposure.",posted:"10 days ago"},
  ]},

  // ── Marylebone ──
  { id:"flashpoint",name:"Flashpoint VC",initials:"FP",focus:"Secondaries",neighborhood:"Marylebone",
    lat:51.5195,lng:-0.1468, // 53 New Cavendish Street, W1G 9TG
    aum:"€500M",founded:2019,website:"https://flashpointvc.com",hiring:true,roles:[
    {title:"Investment Associate — Secondary Fund",freshness:"HOT",source:"linkedin",url:"#",description:"Supporting secondary transactions across European VC portfolios. Strong modelling, LP/GP dynamics, and complex structures.",posted:"2 days ago"},
  ]},

  // ── King's Cross ──
  { id:"balderton",name:"Balderton Capital",initials:"BC",focus:"Early Stage",neighborhood:"King's Cross",
    lat:51.5305,lng:-0.1199, // 28 Britannia Street, WC1X 9JF
    aum:"€3.7B",founded:2000,website:"https://www.balderton.com",hiring:false,roles:[]},
  { id:"localglobe",name:"LocalGlobe",initials:"LG",focus:"Pre-seed / Seed",neighborhood:"King's Cross",
    lat:51.5335,lng:-0.1270, // 1-2 Brill Place, NW1 1EL
    aum:"€900M",founded:2015,website:"https://localglobe.vc",hiring:false,roles:[]},

  // ── Clerkenwell ──
  { id:"passion",name:"Passion Capital",initials:"PC",focus:"Pre-seed / Seed",neighborhood:"Clerkenwell",
    lat:51.5228,lng:-0.1052, // 65 Clerkenwell Road, EC1R 5BL
    aum:"£100M",founded:2011,website:"https://www.passioncapital.com",hiring:false,roles:[]},
  { id:"playfair",name:"Playfair Capital",initials:"PF",focus:"Pre-seed / Seed",neighborhood:"Clerkenwell",
    lat:51.5235,lng:-0.1063, // 8 Warner Yard, EC1R 5EY
    aum:"£150M",founded:2013,website:"https://playfair.vc",hiring:false,roles:[]},

  // ── Bloomsbury / Holborn ──
  { id:"hoxton",name:"Hoxton Ventures",initials:"HV",focus:"Pre-seed / Seed",neighborhood:"Bloomsbury",
    lat:51.5170,lng:-0.1268, // 55 New Oxford Street, WC1A 1BS
    aum:"€200M",founded:2013,website:"https://hoxtonventures.com",hiring:false,roles:[]},
  { id:"octopus",name:"Octopus Ventures",initials:"OV",focus:"Early Stage",neighborhood:"Holborn",
    lat:51.5185,lng:-0.1090, // 33 Holborn, EC1N 2HT
    aum:"£1.9B",founded:2000,website:"https://octopusventures.com",hiring:true,roles:[
    {title:"Investment Manager — Health",freshness:"WARM",source:"linkedin",url:"#",description:"Sector-focused role covering digital health and biotech. Sourcing through board-level portfolio support.",posted:"2 weeks ago"},
  ]},
];

export default MOCK_FUNDS;
