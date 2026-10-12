// Shows the server's own message when it sends a plain-text one (for example "Patient already has an active monitoring session").
export const errorText = (e, fallback) => (typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : fallback);
