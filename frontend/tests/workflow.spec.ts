import { test, expect } from "@playwright/test";
import path from "node:path";

test("register, upload, profile, chart, save and export", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "New to EK-Logic? Create an account" })
    .click();
  await page.getByLabel("Your name").fill("Integration Test");
  await page
    .getByLabel("Organization", { exact: true })
    .fill("Example organization");
  await page.getByLabel("Email address").fill(`test-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("test-only-password-123");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "A clearer view of your business." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add dataset", exact: true }).click();
  await page
    .getByLabel("Choose file")
    .setInputFiles(path.resolve("../examples/public_health_demo.csv"));
  await page.getByRole("button", { name: "Upload and profile" }).click();
  await expect(
    page.getByRole("heading", { name: "Know your data" }),
  ).toBeVisible();
  await page.getByLabel("Group by", { exact: true }).selectOption("district");
  await page.getByLabel("Measure", { exact: true }).selectOption("visits");
  await page.getByRole("button", { name: "Generate chart" }).click();
  await page.getByText("View accessible chart data", { exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "201", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "167", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Analysis name").fill("District visits");
  await page
    .getByRole("button", { name: "Save analysis", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Analysis saved." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Saved Reports", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "District visits" }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "CSV", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("eklogic-report.csv");
});
