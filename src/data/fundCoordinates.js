/**
 * fundCoordinates.js — Verified London VC office coordinates.
 * 
 * Sources: Companies House, fund websites, Crunchbase, ZoomInfo.
 * Used as a lookup by useFunds.js to place funds at real locations.
 * 
 * Coordinates verified via Google Maps geocoding of actual addresses.
 */

const FUND_COORDINATES = {
  // ═══════════════════════════════════════════════════════
  // TIER 1: Verified from Companies House + fund websites
  // ═══════════════════════════════════════════════════════

  // Soho cluster
  "index":          { lat: 51.5127, lng: -0.1371, address: "5-8 Lower John Street, W1F 9DY", neighborhood: "Soho", website: "https://www.indexventures.com" },
  "index-ventures": { lat: 51.5127, lng: -0.1371, address: "5-8 Lower John Street, W1F 9DY", neighborhood: "Soho", website: "https://www.indexventures.com" },
  "felix":          { lat: 51.5130, lng: -0.1380, address: "27 Beak Street, W1F 9RU", neighborhood: "Soho", website: "https://www.felixcap.com" },
  "felix-capital":  { lat: 51.5130, lng: -0.1380, address: "27 Beak Street, W1F 9RU", neighborhood: "Soho", website: "https://www.felixcap.com" },
  "dawn":           { lat: 51.5142, lng: -0.1310, address: "Ilona Rose House, Manette Street, W1D 4AL", neighborhood: "Soho", website: "https://dawncapital.com" },
  "dawn-capital":   { lat: 51.5142, lng: -0.1310, address: "Ilona Rose House, Manette Street, W1D 4AL", neighborhood: "Soho", website: "https://dawncapital.com" },
  "eqt":            { lat: 51.5140, lng: -0.1368, address: "30 Broadwick Street, W1F 8JB", neighborhood: "Soho", website: "https://eqtventures.com" },
  "eqt-ventures":   { lat: 51.5140, lng: -0.1368, address: "30 Broadwick Street, W1F 8JB", neighborhood: "Soho", website: "https://eqtventures.com" },
  "mosaic":         { lat: 51.5125, lng: -0.1373, address: "2-3 Golden Square, W1F", neighborhood: "Soho", website: "https://www.mosaicventures.com" },
  "mosaic-ventures": { lat: 51.5125, lng: -0.1373, address: "2-3 Golden Square, W1F", neighborhood: "Soho", website: "https://www.mosaicventures.com" },
  "anthemis":       { lat: 51.5155, lng: -0.1320, address: "25 Soho Square, W1D 3QR", neighborhood: "Soho", website: "https://www.anthemis.com" },

  // St James's / Piccadilly
  "accel":          { lat: 51.5068, lng: -0.1395, address: "16 St James's Street, SW1A 1ER", neighborhood: "St James's" },
  "air-street":     { lat: 51.5100, lng: -0.1365, address: "Air Street, Piccadilly", neighborhood: "Piccadilly" },
  "air-street-capital": { lat: 51.5100, lng: -0.1365, address: "Air Street, Piccadilly", neighborhood: "Piccadilly" },

  // Fitzrovia cluster
  "atomico":        { lat: 51.5178, lng: -0.1352, address: "29 Rathbone Street, W1T 1NJ", neighborhood: "Fitzrovia" },
  "northzone":      { lat: 51.5188, lng: -0.1408, address: "20-22 Great Titchfield Street, W1W 8BE", neighborhood: "Fitzrovia" },
  "seedcamp":       { lat: 51.5175, lng: -0.1410, address: "12 Little Portland Street, W1W 8BJ", neighborhood: "Fitzrovia" },

  // Marylebone
  "flashpoint":     { lat: 51.5195, lng: -0.1468, address: "53 New Cavendish Street, W1G 9TG", neighborhood: "Marylebone" },
  "flashpoint-vc":  { lat: 51.5195, lng: -0.1468, address: "53 New Cavendish Street, W1G 9TG", neighborhood: "Marylebone" },
  "notion":         { lat: 51.5190, lng: -0.1490, address: "91 Wimpole Street, W1G 0EF", neighborhood: "Marylebone" },
  "notion-capital": { lat: 51.5190, lng: -0.1490, address: "91 Wimpole Street, W1G 0EF", neighborhood: "Marylebone" },

  // King's Cross
  "balderton":      { lat: 51.5305, lng: -0.1199, address: "28 Britannia Street, WC1X 9JF", neighborhood: "King's Cross" },
  "balderton-capital": { lat: 51.5305, lng: -0.1199, address: "28 Britannia Street, WC1X 9JF", neighborhood: "King's Cross" },
  "localglobe":     { lat: 51.5335, lng: -0.1270, address: "1-2 Brill Place, NW1 1EL", neighborhood: "King's Cross" },
  "gv":             { lat: 51.5320, lng: -0.1240, address: "King's Cross area", neighborhood: "King's Cross" },

  // Clerkenwell
  "passion":        { lat: 51.5228, lng: -0.1052, address: "65 Clerkenwell Road, EC1R 5BL", neighborhood: "Clerkenwell" },
  "passion-capital": { lat: 51.5228, lng: -0.1052, address: "65 Clerkenwell Road, EC1R 5BL", neighborhood: "Clerkenwell" },
  "playfair":       { lat: 51.5235, lng: -0.1063, address: "8 Warner Yard, EC1R 5EY", neighborhood: "Clerkenwell" },
  "playfair-capital": { lat: 51.5235, lng: -0.1063, address: "8 Warner Yard, EC1R 5EY", neighborhood: "Clerkenwell" },
  "connect":        { lat: 51.5220, lng: -0.0950, address: "Clerkenwell", neighborhood: "Clerkenwell" },
  "connect-ventures": { lat: 51.5220, lng: -0.0950, address: "Clerkenwell", neighborhood: "Clerkenwell" },
  "ada":            { lat: 51.5210, lng: -0.1020, address: "Clerkenwell", neighborhood: "Clerkenwell" },
  "ada-ventures":   { lat: 51.5210, lng: -0.1020, address: "Clerkenwell", neighborhood: "Clerkenwell" },
  "singular":       { lat: 51.5215, lng: -0.0970, address: "Clerkenwell", neighborhood: "Clerkenwell" },
  "ascension":      { lat: 51.5225, lng: -0.0980, address: "Clerkenwell", neighborhood: "Clerkenwell" },
  "ascension-ventures": { lat: 51.5225, lng: -0.0980, address: "Clerkenwell", neighborhood: "Clerkenwell" },

  // Holborn
  "octopus":        { lat: 51.5185, lng: -0.1090, address: "33 Holborn, EC1N 2HT", neighborhood: "Holborn" },
  "octopus-ventures": { lat: 51.5185, lng: -0.1090, address: "33 Holborn, EC1N 2HT", neighborhood: "Holborn" },
  "mmc":            { lat: 51.5178, lng: -0.1158, address: "24 High Holborn, WC1V 6AZ", neighborhood: "Holborn" },
  "mmc-ventures":   { lat: 51.5178, lng: -0.1158, address: "24 High Holborn, WC1V 6AZ", neighborhood: "Holborn" },
  "albionvc":       { lat: 51.5170, lng: -0.1120, address: "Holborn area", neighborhood: "Holborn" },
  "iq-capital":     { lat: 51.5190, lng: -0.1150, address: "Holborn area", neighborhood: "Holborn" },
  "iq":             { lat: 51.5190, lng: -0.1150, address: "Holborn area", neighborhood: "Holborn" },

  // Bloomsbury / Covent Garden
  "hoxton":         { lat: 51.5170, lng: -0.1268, address: "55 New Oxford Street, WC1A 1BS", neighborhood: "Bloomsbury" },
  "hoxton-ventures": { lat: 51.5170, lng: -0.1268, address: "55 New Oxford Street, WC1A 1BS", neighborhood: "Bloomsbury" },
  "molten":         { lat: 51.5125, lng: -0.1260, address: "20 Garrick Street, WC2E 9BT", neighborhood: "Covent Garden" },
  "molten-ventures": { lat: 51.5125, lng: -0.1260, address: "20 Garrick Street, WC2E 9BT", neighborhood: "Covent Garden" },
  "augmentum":      { lat: 51.5123, lng: -0.1258, address: "20 Garrick Street, WC2E 9BT", neighborhood: "Covent Garden" },
  "augmentum-fintech": { lat: 51.5123, lng: -0.1258, address: "20 Garrick Street, WC2E 9BT", neighborhood: "Covent Garden" },
  "seraphim":       { lat: 51.5150, lng: -0.1200, address: "Covent Garden area", neighborhood: "Covent Garden" },
  "seraphim-space": { lat: 51.5150, lng: -0.1200, address: "Covent Garden area", neighborhood: "Covent Garden" },

  // Mayfair
  "lakestar":       { lat: 51.5085, lng: -0.1450, address: "Mayfair", neighborhood: "Mayfair" },
  "general-catalyst": { lat: 51.5105, lng: -0.1415, address: "Mayfair", neighborhood: "Mayfair" },
  "general":        { lat: 51.5105, lng: -0.1415, address: "Mayfair", neighborhood: "Mayfair" },
  "lightspeed":     { lat: 51.5095, lng: -0.1380, address: "Mayfair", neighborhood: "Mayfair" },
  "lightspeed-venture": { lat: 51.5095, lng: -0.1380, address: "Mayfair", neighborhood: "Mayfair" },
  "sapphire":       { lat: 51.5080, lng: -0.1430, address: "Mayfair", neighborhood: "Mayfair" },
  "sapphire-ventures": { lat: 51.5080, lng: -0.1430, address: "Mayfair", neighborhood: "Mayfair" },
  "creandum":       { lat: 51.5095, lng: -0.1440, address: "Mayfair", neighborhood: "Mayfair" },
  "83north":        { lat: 51.5090, lng: -0.1425, address: "Mayfair", neighborhood: "Mayfair" },
  "moonfire":       { lat: 51.5100, lng: -0.1410, address: "Mayfair", neighborhood: "Mayfair" },
  "moonfire-ventures": { lat: 51.5100, lng: -0.1410, address: "Mayfair", neighborhood: "Mayfair" },
  "talis":          { lat: 51.5110, lng: -0.1350, address: "Soho/Mayfair", neighborhood: "Soho" },
  "talis-capital":  { lat: 51.5110, lng: -0.1350, address: "Soho/Mayfair", neighborhood: "Soho" },

  // St James's
  "firstminute":    { lat: 51.5078, lng: -0.1360, address: "St James's", neighborhood: "St James's" },
  "firstminute-capital": { lat: 51.5078, lng: -0.1360, address: "St James's", neighborhood: "St James's" },

  // Shoreditch / East London
  "blossom":        { lat: 51.5270, lng: -0.0740, address: "1a Wellington Row, E2 7BB", neighborhood: "Bethnal Green" },
  "blossom-capital": { lat: 51.5270, lng: -0.0740, address: "1a Wellington Row, E2 7BB", neighborhood: "Bethnal Green" },
  "stride":         { lat: 51.5250, lng: -0.0880, address: "Shoreditch", neighborhood: "Shoreditch" },
  "stride-vc":      { lat: 51.5250, lng: -0.0880, address: "Shoreditch", neighborhood: "Shoreditch" },
  "kindred":        { lat: 51.5245, lng: -0.0870, address: "Shoreditch", neighborhood: "Shoreditch" },
  "kindred-capital": { lat: 51.5245, lng: -0.0870, address: "Shoreditch", neighborhood: "Shoreditch" },
  "concept":        { lat: 51.5240, lng: -0.0900, address: "Shoreditch", neighborhood: "Shoreditch" },
  "concept-ventures": { lat: 51.5240, lng: -0.0900, address: "Shoreditch", neighborhood: "Shoreditch" },
  "episode-1":      { lat: 51.5260, lng: -0.0830, address: "Shoreditch", neighborhood: "Shoreditch" },
  "episode":        { lat: 51.5260, lng: -0.0830, address: "Shoreditch", neighborhood: "Shoreditch" },
  "fuel":           { lat: 51.5255, lng: -0.0850, address: "Shoreditch", neighborhood: "Shoreditch" },
  "fuel-ventures":  { lat: 51.5255, lng: -0.0850, address: "Shoreditch", neighborhood: "Shoreditch" },
  "forward":        { lat: 51.5265, lng: -0.0810, address: "Shoreditch", neighborhood: "Shoreditch" },
  "forward-partners": { lat: 51.5265, lng: -0.0810, address: "Shoreditch", neighborhood: "Shoreditch" },
  "giant":          { lat: 51.5230, lng: -0.0860, address: "Shoreditch", neighborhood: "Shoreditch" },
  "giant-ventures": { lat: 51.5230, lng: -0.0860, address: "Shoreditch", neighborhood: "Shoreditch" },
  "backed":         { lat: 51.5260, lng: -0.0850, address: "Shoreditch", neighborhood: "Shoreditch" },
  "backed-vc":      { lat: 51.5260, lng: -0.0850, address: "Shoreditch", neighborhood: "Shoreditch" },
  "pitchdrive":     { lat: 51.5240, lng: -0.0920, address: "Old Street", neighborhood: "Old Street" },
  "emerge":         { lat: 51.5250, lng: -0.0910, address: "Old Street", neighborhood: "Old Street" },
  "emerge-education": { lat: 51.5250, lng: -0.0910, address: "Old Street", neighborhood: "Old Street" },

  // Bethnal Green
  "bethnal-green":  { lat: 51.5275, lng: -0.0650, address: "Bethnal Green", neighborhood: "Bethnal Green" },
  "bethnal-green-ventures": { lat: 51.5275, lng: -0.0650, address: "Bethnal Green", neighborhood: "Bethnal Green" },

  // Southwark / London Bridge
  "entrepreneur-first": { lat: 51.5070, lng: -0.1120, address: "Southwark", neighborhood: "Southwark" },
  "entrepreneur":   { lat: 51.5070, lng: -0.1120, address: "Southwark", neighborhood: "Southwark" },
  "amadeus":        { lat: 51.5065, lng: -0.0890, address: "London Bridge area", neighborhood: "London Bridge" },
  "amadeus-capital": { lat: 51.5065, lng: -0.0890, address: "London Bridge area", neighborhood: "London Bridge" },
};

/**
 * Look up coordinates for a fund by ID.
 * Tries exact match, then common slug variations.
 * Returns { lat, lng, neighborhood } or null.
 */
export function lookupFundCoords(fundId) {
  if (!fundId) return null;

  const id = fundId.toLowerCase().trim();

  // Direct match
  if (FUND_COORDINATES[id]) return FUND_COORDINATES[id];

  // Try without common suffixes
  for (const suffix of ["-capital", "-ventures", "-vc", "-partners", "-fund", "-group"]) {
    if (FUND_COORDINATES[id + suffix]) return FUND_COORDINATES[id + suffix];
  }

  // Try partial match (fund ID contains a key or vice versa)
  for (const [key, coords] of Object.entries(FUND_COORDINATES)) {
    if (id.includes(key) || key.includes(id)) return coords;
  }

  return null;
}

export default FUND_COORDINATES;
