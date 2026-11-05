import { afterEach, describe, expect, it, vi } from "vitest";
import { checkFile } from "../pages/Import";
import { api, ApiError, query } from "./api";
import { fmt, scoreBand } from "./format";

afterEach(() => vi.restoreAllMocks());

describe("format", () => {
  it("formate en français", () => {
    expect(fmt.int(1234)).toBe("1 234");
    expect(fmt.score(92.4)).toBe("92,4");
    expect(fmt.score(null)).toBe("—");
    expect(fmt.price("34.90")).toBe("34,90 €");
    expect(fmt.price("abc")).toBe("abc");
    expect(fmt.price("")).toBe("—");
    expect(fmt.signed(-46)).toBe("−46");
    expect(fmt.signed(4.3, 1)).toBe("+4,3");
    expect(fmt.plural(1, "anomalie", "anomalies")).toBe("1 anomalie");
    expect(fmt.plural(2, "anomalie", "anomalies")).toBe("2 anomalies");
    expect(fmt.percent(93, 144)).toBe("65 %");
  });

  it("classe l'indice selon les seuils de l'API", () => {
    expect([100, 90, 89, 70, 69, 40, 39, 0].map(scoreBand)).toEqual([
      "excellent", "excellent", "good", "good", "fair", "fair", "poor", "poor",
    ]);
    expect(scoreBand(null)).toBe("none");
  });
});

describe("contrôle du fichier côté navigateur", () => {
  const file = (name: string, size: number) => new File([new Uint8Array(size)], name);
  it("accepte un CSV raisonnable", () => expect(checkFile(file("catalogue.CSV", 10))).toBeNull());
  it("refuse une autre extension", () => expect(checkFile(file("catalogue.xlsx", 10))).toMatch(/pas un \.csv/));
  it("refuse un fichier vide", () => expect(checkFile(file("a.csv", 0))).toMatch(/vide/));
  it("refuse plus de 2 Mo", () => expect(checkFile(file("a.csv", 2_000_001))).toMatch(/2 Mo/));
});

describe("client API", () => {
  it("construit la query en ignorant les valeurs vides", () => {
    expect(query({ a: "x", b: "", c: undefined, d: null, e: 0, f: false })).toBe("?a=x&e=0&f=false");
    expect(query({})).toBe("");
  });

  it("transforme une erreur structurée en ApiError", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Ligne 3 : product_id dupliqué", code: "invalid_catalog", errors: [{ line: 3, column: "product_id", message: "x" }] }), { status: 422 }),
    );
    const error = await api.audits().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, code: "invalid_catalog", message: "Ligne 3 : product_id dupliqué" });
    expect((error as ApiError).errors[0]?.line).toBe(3);
  });

  it("signale clairement une API injoignable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(api.audits()).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("encode les identifiants produits dans l'URL", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
    await api.product(3, "a b/c?d");
    expect(spy.mock.calls[0]?.[0]).toBe("/api/audits/3/products/a%20b/c%3Fd");
  });

  it("gère une réponse 204 sans corps", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.deleteAudit(1)).resolves.toBeUndefined();
  });
});
