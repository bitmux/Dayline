/**
 * The webfont link, shared by both cards.
 *
 * One id and one href on purpose: whichever card mounts first installs the link
 * and the other finds it already there. When these were two copies of the same
 * two constants, adding a family to one card silently gave the other card
 * whichever list happened to load first.
 */
const FONT_LINK_ID = "day-spine-card-fonts";
const FONT_HREF =
  "https://fonts.googleapis.com/css2?family=Caprasimo&family=Figtree:wght@400;500;600;700" +
  // Roboto is what Home Assistant's own frontend is set in, so a clock in it
  // looks native on a dashboard rather than like a card with opinions. It is
  // already loaded inside HA; this is for the dev harness and for anywhere else
  // the bundle gets opened.
  "&family=Roboto:wght@300;400;500&display=swap";

export function loadFonts(): void {
  if (document.getElementById(FONT_LINK_ID)) return;
  const link = document.createElement("link");
  link.id = FONT_LINK_ID;
  link.rel = "stylesheet";
  link.href = FONT_HREF;
  document.head.appendChild(link);
}
