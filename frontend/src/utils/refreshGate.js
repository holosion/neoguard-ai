// Permit one refresh at a time; invalidate responses after a view changes.
export class RefreshGate {
  active = null;
  start() {
    if (this.active) return null;
    this.active = {};
    return this.active;
  }
  isCurrent(token) { return this.active === token; }
  finish(token) { if (this.isCurrent(token)) this.active = null; }
  invalidate() { this.active = null; }
}
