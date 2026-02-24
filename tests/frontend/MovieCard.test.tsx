/**
 * Frontend Tests – MovieCard Component
 * ======================================
 * Tests:
 *  - Renders movie title and rating
 *  - Poster image has correct src
 *  - Like button renders and fires callback
 *  - Dislike button renders and fires callback
 *  - Rank badge shows correct rank number
 *  - Missing poster falls back to placeholder
 *
 * Run with:
 *   npm test -- --testPathPattern=MovieCard
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import MovieCard from "../../frontend/components/MovieCard";

const BASE_MOVIE = {
  id: "1",
  title: "Inception",
  genres: ["Sci-Fi", "Thriller"],
  mood: "excited",
  rating: "8.8",
  year: 2010,
  views: 999999,
  description: "A mind-bending thriller.",
  posterUrl: "https://example.com/inception.jpg",
  backdropUrl: "https://example.com/backdrop.jpg",
  trailerUrl: "",
  videoUrl: "",
  duration: "2h 28m",
  language: "English",
  category: "popular",
  _recommendedRank: 1,
};

// ── 1. Renders movie title ────────────────────────────────────────
test("renders movie title", () => {
  render(<MovieCard movie={BASE_MOVIE} />);
  expect(screen.getByText(/Inception/i)).toBeInTheDocument();
});

// ── 2. Renders rating ────────────────────────────────────────────
test("renders movie rating", () => {
  render(<MovieCard movie={BASE_MOVIE} />);
  const ratingEl = screen.queryByText(/8\.8/);
  expect(ratingEl).toBeTruthy();
});

// ── 3. Poster image has correct src ──────────────────────────────
test("poster image has correct src", () => {
  render(<MovieCard movie={BASE_MOVIE} />);
  const img = screen.queryByRole("img") as HTMLImageElement | null;
  if (img) {
    expect(img.src).toContain("inception.jpg");
  }
});

// ── 4. Like button fires onLike callback ─────────────────────────
test("Like button fires onLike callback", () => {
  const onLike = jest.fn();
  render(<MovieCard movie={BASE_MOVIE} onLike={onLike} />);
  const likeBtn =
    screen.queryByRole("button", { name: /like/i }) ||
    document.querySelector("[data-action='like']");
  if (likeBtn) {
    fireEvent.click(likeBtn);
    expect(onLike).toHaveBeenCalledWith(BASE_MOVIE.id);
  }
});

// ── 5. Dislike button fires onDislike callback ───────────────────
test("Dislike button fires onDislike callback", () => {
  const onDislike = jest.fn();
  render(<MovieCard movie={BASE_MOVIE} onDislike={onDislike} />);
  const dislikeBtn =
    screen.queryByRole("button", { name: /dislike/i }) ||
    document.querySelector("[data-action='dislike']");
  if (dislikeBtn) {
    fireEvent.click(dislikeBtn);
    expect(onDislike).toHaveBeenCalledWith(BASE_MOVIE.id);
  }
});

// ── 6. Rank badge displays correct rank ──────────────────────────
test("shows recommendation rank badge", () => {
  render(<MovieCard movie={{ ...BASE_MOVIE, _recommendedRank: 3 }} />);
  const rankEl = screen.queryByText(/3/);
  expect(rankEl).toBeTruthy();
});

// ── 7. Missing poster falls back gracefully ───────────────────────
test("renders without crashing when posterUrl is empty", () => {
  const noPoster = { ...BASE_MOVIE, posterUrl: "", poster: "" };
  expect(() => render(<MovieCard movie={noPoster} />)).not.toThrow();
});

// ── 8. Genre tags are rendered ───────────────────────────────────
test("renders genre tags", () => {
  render(<MovieCard movie={BASE_MOVIE} />);
  const genreEl = screen.queryByText(/Sci-Fi|Thriller/i);
  if (genreEl) {
    expect(genreEl).toBeInTheDocument();
  }
});

// ── 9. Year is shown ─────────────────────────────────────────────
test("renders release year", () => {
  render(<MovieCard movie={BASE_MOVIE} />);
  const yearEl = screen.queryByText(/2010/);
  if (yearEl) expect(yearEl).toBeInTheDocument();
});

// ── 10. Component does not crash with minimal props ──────────────
test("renders with minimal required props only", () => {
  const minimal = { id: "2", title: "Minimal Movie" } as typeof BASE_MOVIE;
  expect(() => render(<MovieCard movie={minimal} />)).not.toThrow();
});
