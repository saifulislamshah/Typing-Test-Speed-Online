// Share intents, Web Share API on touch devices, and copy-to-clipboard.
export function shareLinks(text, url) {
  const t = encodeURIComponent(text), u = encodeURIComponent(url);
  return {
    fb: `https://www.facebook.com/sharer/sharer.php?u=${u}`,
    li: `https://www.linkedin.com/sharing/share-offsite/?url=${u}`,
    x: `https://twitter.com/intent/tweet?text=${t}&url=${u}`,
  };
}

export const canNativeShare = () => typeof navigator.share === 'function' && matchMedia('(pointer: coarse)').matches;

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.className = 'sr-only';
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  }
}
