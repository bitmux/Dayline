/**
 * The bundle's entry point: both cards, one file.
 *
 * They share a feed, a palette and a button implementation, and /config/www/ is
 * a flat directory rather than a module graph — so shipping them separately
 * would mean two resources to register and two chances to register only one.
 * The output is still named day-spine-card.js, because that is the filename
 * every existing install and the integration's own frontend registration
 * already point at.
 */
import "./day-spine-card";
import "./dayline-glance-card";
