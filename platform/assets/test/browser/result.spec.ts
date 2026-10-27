import {type APIRequestContext, type Page} from "@playwright/test"
import {expect, test} from "./support/test"
import {layoutProblems, publishResult, watchErrors} from "./support/visitor"

// A published Result's page at a desktop and a phone width: it works, and the
// picture a shared link to it shows is the Result's own, a 1200 by 630 PNG
// drawn for it, while every other page keeps the site's picture.
let digest: string
test.beforeAll(() => {
  digest = publishResult()
})

async function sharedPicture(page: Page) {
  const meta = (property: string) => page.locator(`meta[property="${property}"]`).getAttribute("content")
  return {url: (await meta("og:image")) as string, alt: (await meta("og:image:alt")) as string}
}

// The picture's address answers with a PNG, and the size its header names.
async function pngSize(request: APIRequestContext, url: string) {
  const response = await request.get(url)
  expect(response.status()).toBe(200)
  expect(response.headers()["content-type"]).toBe("image/png")
  const body = await response.body()
  expect(body.subarray(0, 8)).toEqual(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
  return {width: body.readUInt32BE(16), height: body.readUInt32BE(20)}
}

for (const width of [1280, 390]) {
  test.describe(`${width} wide`, () => {
    test.use({viewport: {width, height: 844}, isMobile: width < 768, hasTouch: width < 768})

    test("a Result's page works and shares its own picture", async ({page, baseURL}) => {
      const errors = watchErrors(page)
      const response = await page.goto(`/results/${digest}`, {waitUntil: "networkidle"})
      expect(response?.status()).toBe(200)
      await expect(page.locator("#run-comparison")).toBeVisible()
      await expect(page.locator(".phx-connected").first()).toBeAttached()
      expect(await layoutProblems(page)).toEqual([])
      expect(errors).toEqual([])

      const picture = await sharedPicture(page)
      expect(picture.url).toBe(`${baseURL}/results/${encodeURIComponent(digest)}/share.png`)
      expect(picture.alt).toContain("Improved")
      expect(await pngSize(page.request, picture.url)).toEqual({width: 1200, height: 630})
    })

    test("the list of Results keeps the site's picture", async ({page, baseURL}) => {
      await page.goto("/results", {waitUntil: "networkidle"})
      const picture = await sharedPicture(page)
      expect(picture.url).toBe(`${baseURL}/images/techtree-share.png`)
      expect(await pngSize(page.request, picture.url)).toEqual({width: 1200, height: 630})
    })
  })
}
