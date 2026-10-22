#pragma once
// Older FastAPI deployments can match "runtime" as a dynamic device ID and
// return an auth/validation error rather than 404. The legacy route still
// authenticates the same device credential; throttling must not be bypassed.
inline bool useLegacyContext(int status) {
  return status >= 400 && status < 500 && status != 429;
}
