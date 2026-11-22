import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import {
  apiCreateReadyAccount,
  apiSignIn,
  env,
  MAIN_ADMIN_PASSWORD,
  NEW_PASSWORD,
  signIn,
} from "./helpers";

/**
 * «موقع البيت» inputs (docs/system.md §5.2 v1.6): a typed coordinate or a pasted Google Maps link,
 * the place search (Places, Iraq only, Arabic), and the phone's GPS. The e2e stack has no Maps
 * key, so the search test serves a fake key and a fake `window.google`; nothing reaches Google.
 * All coordinates are public places, not subscriber homes.
 */

const PROJECT_INDEX: Record<string, number> = {
  "desktop-chrome": 0,
  "pixel-7": 1,
  "iphone-14": 2,
};

async function marketer(request: APIRequestContext, project: string) {
  const i = PROJECT_INDEX[project] ?? 3;
  const m = { name: `مسوّق الموقع ${i}`, phone: `0770000040${i}` };
  const login = await request.post("/api/auth/login", {
    data: { phone: m.phone, password: NEW_PASSWORD },
  });
  if (login.status() !== 200) {
    const main = await apiSignIn(
      request,
      env("SUPERADMIN_PHONE"),
      MAIN_ADMIN_PASSWORD,
    );
    await apiCreateReadyAccount(request, main, "marketers", m);
  }
  return m;
}

async function openNewForm(page: Page, phone: string) {
  await signIn(page, phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/drafts/new");
}

const coords = (page: Page) => page.getByTestId("location-coords");
const saved = (page: Page) =>
  expect(page.getByTestId("save-badge")).toHaveText("محفوظ");

async function goToCoordinate(page: Page, text: string) {
  await page.getByTestId("coordinate-input").fill(text);
  await page.getByTestId("coordinate-go").click();
}

test("a typed coordinate or a Google Maps link moves the pin and is saved; outside Iraq is refused", async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(90_000);
  const m = await marketer(request, testInfo.project.name);
  await openNewForm(page, m.phone);

  // No key in the e2e stack: the map is unavailable, the coordinate box still works.
  await expect(page.getByTestId("map-unavailable")).toBeVisible();
  await expect(page.getByTestId("place-search")).toHaveCount(0);

  await goToCoordinate(page, "43.68, 34.70");
  await expect(
    page.getByText("يبدو أن خط العرض وخط الطول مقلوبان", { exact: false }),
  ).toBeVisible();
  await goToCoordinate(page, "33.89, 35.50");
  await expect(
    page.getByText("الموقع خارج العراق، تأكد من الإحداثيات"),
  ).toBeVisible();
  await goToCoordinate(page, "https://maps.app.goo.gl/AbCdEf123");
  await expect(
    page.getByText("الروابط المختصرة", { exact: false }),
  ).toBeVisible();
  await expect(page.getByTestId("location-status")).toHaveText(
    "لم يُحدَّد موقع البيت بعد",
  );

  await goToCoordinate(page, "34.70, 43.68");
  await expect(coords(page)).toHaveText("34.700000, 43.680000");
  await expect(page).toHaveURL(/\/drafts\/[0-9a-f-]{36}$/);
  await saved(page);

  await goToCoordinate(
    page,
    "https://www.google.com/maps/@36.1911,44.0092,17z",
  );
  await expect(coords(page)).toHaveText("36.191100, 44.009200");
  await saved(page);

  await page.reload();
  await expect(coords(page)).toHaveText("36.191100, 44.009200");
});

test("«استخدم موقعي الحالي» uses the phone GPS; a position outside Iraq is not saved", async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(90_000);
  const m = await marketer(request, testInfo.project.name);
  await page.context().grantPermissions(["geolocation"]);
  await page.context().setGeolocation({ latitude: 33.89, longitude: 35.5 });
  await openNewForm(page, m.phone);

  await page.getByRole("button", { name: "استخدم موقعي الحالي" }).click();
  await expect(page.getByTestId("location-error")).toContainText(
    "موقعك الحالي خارج العراق",
  );
  await expect(page.getByTestId("location-status")).toHaveText(
    "لم يُحدَّد موقع البيت بعد",
  );

  await page
    .context()
    .setGeolocation({ latitude: 30.5085, longitude: 47.7804, accuracy: 9 });
  await page.getByRole("button", { name: "استخدم موقعي الحالي" }).click();
  await expect(coords(page)).toHaveText("30.508500, 47.780400");
  await expect(page.getByTestId("location-status")).toContainText(
    "دقة تقريبية 9 م",
  );
  await saved(page);
});

/** A fake Google Maps API: a blank map, a marker, and Places returning one public square. */
function installFakeGoogle() {
  const w = window as unknown as Record<string, unknown>;
  const requests: unknown[] = [];
  w.__placesRequests = requests;
  class FakeMap {
    constructor(el: HTMLElement) {
      el.style.background = "#444";
    }
    panTo() {}
    setZoom() {}
    addListener() {
      return { remove() {} };
    }
  }
  class FakeMarker {
    map: unknown;
    position: unknown;
    constructor(opts: { map: unknown; position: unknown }) {
      this.map = opts.map;
      this.position = opts.position;
    }
    addListener() {
      return { remove() {} };
    }
  }
  class LatLng {
    constructor(
      private a: number,
      private b: number,
    ) {}
    lat() {
      return this.a;
    }
    lng() {
      return this.b;
    }
  }
  const prediction = {
    placeId: "fake-tahrir",
    mainText: { text: "ساحة التحرير" },
    secondaryText: { text: "بغداد، العراق" },
    toPlace() {
      const place = {
        location: undefined as unknown,
        async fetchFields() {
          place.location = new LatLng(33.3336, 44.4342);
        },
      };
      return place;
    },
  };
  const places = {
    AutocompleteSessionToken: class {},
    AutocompleteSuggestion: {
      async fetchAutocompleteSuggestions(req: Record<string, unknown>) {
        requests.push({ ...req, sessionToken: Boolean(req.sessionToken) });
        return { suggestions: [{ placePrediction: prediction }] };
      },
    },
  };
  w.google = {
    maps: {
      async importLibrary(name: string) {
        if (name === "maps") return { Map: FakeMap };
        if (name === "marker") return { AdvancedMarkerElement: FakeMarker };
        if (name === "places") return places;
        throw new Error(name);
      },
    },
  };
}

test.describe("with a fake Google Maps", () => {
  // The PWA service worker would fetch /api/client-config itself, past page.route (seen on WebKit).
  test.use({ serviceWorkers: "block" });

  test("place search: Iraq-only Arabic suggestions, a pick moves the pin and is saved", async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(90_000);
    const m = await marketer(request, testInfo.project.name);
    await page.addInitScript(installFakeGoogle);
    await page.route("**/api/client-config", (route) =>
      route.fulfill({
        json: {
          maps: {
            api_key: "e2e-fake-key",
            map_id: "",
            default_center: { lat: 33.3152, lng: 44.3661 },
          },
        },
      }),
    );
    await openNewForm(page, m.phone);

    const search = page.getByTestId("place-search");
    await search.fill("ساحة");
    await page.getByRole("option", { name: /ساحة التحرير/ }).click();
    await expect(coords(page)).toHaveText("33.333600, 44.434200");
    await expect(page.getByTestId("map-picker")).toBeVisible();
    await saved(page);

    const sent = await page.evaluate(
      () =>
        (window as unknown as { __placesRequests: unknown[] }).__placesRequests,
    );
    expect(sent[0]).toMatchObject({
      input: "ساحة",
      includedRegionCodes: ["iq"],
      region: "iq",
      language: "ar",
      sessionToken: true,
    });

    await page.reload();
    await expect(coords(page)).toHaveText("33.333600, 44.434200");
  });
});
