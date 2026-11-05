import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { BarList, SeverityStack } from "./charts";
import { HangTag } from "./HangTag";
import { ConfidenceBadge, Pagination, ScoreBadge, SortHeader } from "./ui";

describe("HangTag", () => {
  it("affiche la part de fiches sans anomalie et son niveau", () => {
    render(<HangTag active={144} affected={51} />);
    expect(screen.getByLabelText("65 % des fiches actives sans anomalie")).toBeInTheDocument();
    expect(screen.getByText("93 sur 144 actives")).toBeInTheDocument();
    expect(screen.getByText("Fragile")).toBeInTheDocument();
  });

  it("gère un catalogue sans fiche active", () => {
    render(<HangTag active={0} affected={0} />);
    expect(screen.getByLabelText("Aucune fiche active")).toBeInTheDocument();
  });
});

describe("graphiques", () => {
  it("décrit la répartition des priorités pour les lecteurs d'écran", () => {
    render(<SeverityStack counts={{ high: 11, medium: 22, low: 0 }} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Répartition par priorité. Haute : 11, Moyenne : 22, Basse : 0");
  });

  it("dimensionne les barres par rapport au maximum et rend les liens", () => {
    const { container } = render(
      <MemoryRouter>
        <BarList label="test" items={[{ key: "a", label: "Règle A", value: 10, href: "/issues?code=a" }, { key: "b", label: "Règle B", value: 5 }]} />
      </MemoryRouter>,
    );
    const widths = [...container.querySelectorAll<HTMLElement>(".bar-fill")].map((el) => el.style.width);
    expect(widths).toEqual(["100%", "50%"]);
    expect(screen.getByRole("link", { name: "Règle A" })).toHaveAttribute("href", "/issues?code=a");
  });
});

describe("badges", () => {
  it("distingue constats et heuristiques", () => {
    render(<ConfidenceBadge confidence="heuristic" />);
    expect(screen.getByText("À vérifier")).toHaveAttribute("title", expect.stringContaining("pas une certitude"));
  });

  it("colore l'indice selon son niveau", () => {
    render(<ScoreBadge score={45} />);
    expect(screen.getByText("45")).toHaveClass("score-fair");
  });
});

describe("pagination et tri", () => {
  it("désactive les boutons aux extrémités et annonce la plage", async () => {
    const onPage = vi.fn();
    render(<Pagination page={1} pageSize={25} total={55} onPage={onPage} noun={["anomalie", "anomalies"]} />);
    expect(screen.getByText("1–25 sur 55 anomalies")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Précédent" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Suivant" }));
    expect(onPage).toHaveBeenCalledWith(2);
  });

  it("alterne le sens du tri et l'expose via aria-sort", async () => {
    const onSort = vi.fn();
    const { rerender } = render(
      <table><thead><tr><SortHeader label="Prix" field="price" sort="score" onSort={onSort} /></tr></thead></table>,
    );
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "none");
    await userEvent.click(screen.getByRole("button", { name: "Prix" }));
    expect(onSort).toHaveBeenLastCalledWith("price");
    rerender(<table><thead><tr><SortHeader label="Prix" field="price" sort="price" onSort={onSort} /></tr></thead></table>);
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "ascending");
    await userEvent.click(screen.getByRole("button", { name: "Prix" }));
    expect(onSort).toHaveBeenLastCalledWith("-price");
  });
});
