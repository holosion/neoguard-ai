// Reads the expiry time (in ms) from the sign-in token, or null if it cannot be read.
export function tokenExpiry() {
  try {
    const part = localStorage.getItem('access_token').split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const { exp } = JSON.parse(atob(part));
    return exp ? exp * 1000 : null;
  } catch {
    return null;
  }
}
