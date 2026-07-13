import type {
  ContentIntensity,
  Genre,
  Pov,
  ProtagonistRole,
  SessionConfig,
  TargetLength,
  Tone,
} from "./api";

export const GENRES: { value: Genre; label: string }[] = [
  { value: "fantasy", label: "Fantasy" },
  { value: "scifi", label: "Sci-fi" },
  { value: "horror", label: "Horror" },
  { value: "mystery", label: "Mystery" },
  { value: "romance", label: "Romance" },
  { value: "literary", label: "Literary" },
  { value: "comedy", label: "Comedy" },
];

export const TONES: { value: Tone; label: string }[] = [
  { value: "serious", label: "Serious" },
  { value: "comedic", label: "Comedic" },
  { value: "gothic", label: "Gothic" },
  { value: "cyberpunk", label: "Cyberpunk" },
  { value: "cozy", label: "Cozy" },
  { value: "dark", label: "Dark" },
];

export const POVS: { value: Pov; label: string }[] = [
  { value: "first_person", label: "First person" },
  { value: "third_limited", label: "Third limited" },
  { value: "third_omniscient", label: "Third omniscient" },
];

export const LENGTHS: { value: TargetLength; label: string }[] = [
  { value: "brief", label: "Brief" },
  { value: "medium", label: "Medium" },
  { value: "long", label: "Long" },
];

export const INTENSITIES: { value: ContentIntensity; label: string }[] = [
  { value: "sfw", label: "Safe" },
  { value: "mature", label: "Mature" },
  { value: "dark", label: "Dark" },
];

export const ROLES: { value: ProtagonistRole; label: string }[] = [
  { value: "protagonist", label: "The protagonist" },
  { value: "author", label: "The author" },
  { value: "narrator", label: "A narrator" },
];

function labelOf<T extends string>(options: { value: T; label: string }[], value: T): string {
  return options.find((o) => o.value === value)?.label ?? value;
}

/** Compact one-line summary for the header chip, e.g. "Fantasy · Third limited · Dark". */
export function configSummary(config: SessionConfig): string {
  return [
    labelOf(GENRES, config.genre),
    labelOf(POVS, config.pov),
    labelOf(TONES, config.tone),
  ].join(" · ");
}
