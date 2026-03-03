/**
 * cities.js — City coordinates for globe rendering.
 * Active cities get beacons + labels. Inactive cities get minimal dots.
 */

export const CITIES = {
  london: { name: "LONDON", coord: [-0.1278, 51.5074], label: "51.5074\u00b0N  0.1278\u00b0W", active: true },
};

// Future city nodes — shown as faint dots on the globe
export const INACTIVE_CITIES = [
  [-74.006, 40.7128],    // New York
  [-122.42, 37.77],      // San Francisco
  [2.3522, 48.8566],     // Paris
  [13.405, 52.52],       // Berlin
  [18.07, 59.33],        // Stockholm
  [34.78, 32.08],        // Tel Aviv
  [55.27, 25.2],         // Dubai
  [72.88, 19.08],        // Mumbai
  [103.82, 1.3521],      // Singapore
  [139.69, 35.69],       // Tokyo
  [151.21, -33.87],      // Sydney
  [-46.63, -23.55],      // São Paulo
];
