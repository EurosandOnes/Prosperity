// api/approve.js — Vercel serverless function
// Receives approval decisions from the review page and triggers GitHub Actions.

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
  if (!GITHUB_TOKEN) {
    return res.status(500).json({ error: "GITHUB_TOKEN not configured" });
  }

  try {
    const { approved_hashes, rejected_hashes, decisions } = req.body;

    if (!approved_hashes && !rejected_hashes) {
      return res.status(400).json({ error: "No decisions provided" });
    }

    // First, commit the full decision history for the learning engine
    // We'll store it alongside the approved_roles.json
    const decisionsPayload = JSON.stringify({
      decisions: decisions || [],
      submitted_at: new Date().toISOString(),
    });

    // Trigger the Approve Roles workflow with approved hashes
    const hashStr = (approved_hashes || []).length > 0
      ? approved_hashes.join(",")
      : "none";

    // Also pass rejected hashes via a separate input
    const rejectStr = (rejected_hashes || []).length > 0
      ? rejected_hashes.join(",")
      : "none";

    const response = await fetch(
      "https://api.github.com/repos/EurosandOnes/Prosperity/dispatches",
      {
        method: "POST",
        headers: {
          Authorization: `token ${GITHUB_TOKEN}`,
          Accept: "application/vnd.github.v3+json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          event_type: "approve_roles",
          client_payload: {
            approved: hashStr,
            rejected: rejectStr,
            decisions: decisionsPayload,
          },
        }),
      }
    );

    if (response.ok || response.status === 204) {
      return res.status(200).json({
        success: true,
        approved: (approved_hashes || []).length,
        rejected: (rejected_hashes || []).length,
      });
    } else {
      const errText = await response.text();
      console.error("GitHub API error:", errText);
      return res.status(502).json({ error: "GitHub API failed", details: errText });
    }
  } catch (err) {
    console.error("Approve API error:", err);
    return res.status(500).json({ error: err.message });
  }
}
