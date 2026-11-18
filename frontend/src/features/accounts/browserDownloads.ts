/** The browser adapter owns only temporary anchors/URLs, never account selection or secrets. */
export interface AccountDownloadDependencies {
  document: Document;
  origin: string;
  urls: Pick<typeof URL, 'createObjectURL' | 'revokeObjectURL'>;
  schedule(callback: () => void, delay: number): unknown;
}
export function createAccountDownloads(deps: AccountDownloadDependencies) {
  function start(url: string, filename: string, delay: number, revoke?: () => void): void {
    let anchor: HTMLAnchorElement | undefined;
    const release = () => {try {revoke?.();} finally {anchor?.remove();}};
    try {
      anchor = deps.document.createElement('a');
      anchor.href = url; anchor.download = filename;
      if (!revoke) anchor.rel = 'noopener';
      deps.document.body.appendChild(anchor); anchor.click();
      deps.schedule(release, delay);
    } catch (error) {release(); throw error;}
  }
  return {
    downloadBlob(blob: Blob, filename: string): void {
      const url = deps.urls.createObjectURL(blob);
      start(url, filename, 800, () => deps.urls.revokeObjectURL(url));
    },
    downloadUrl(url: string, filename: string): void {
      let parsed: URL;
      try {parsed = new URL(url, deps.origin);} catch {throw new Error('下载地址必须为同源 HTTP 地址');}
      if (!['http:', 'https:'].includes(parsed.protocol) || parsed.origin !== new URL(deps.origin).origin || parsed.username || parsed.password) {
        throw new Error('下载地址必须为同源 HTTP 地址');
      }
      start(url, filename, 1000);
    },
  };
}
