import { installAuthInterceptors } from "./axiosSetup";
import { toast } from "react-toastify";

jest.mock("react-toastify", () => ({
  toast: {
    dismiss: jest.fn(),
    error: jest.fn(),
  },
}));

function makeClient() {
  return {
    interceptors: {
      response: {
        use: jest.fn(),
      },
    },
  };
}

describe("axiosSetup interceptor", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    document.cookie = "";
  });

  test("dispatches reauth-required on 401 reauth_required (no toast)", async () => {
    const client = makeClient();
    const winSpy = jest.spyOn(window, "dispatchEvent");

    installAuthInterceptors(client, { mode: "default" });
    const [, rejectedHandler] = client.interceptors.response.use.mock.calls[0];

    const error = {
      response: { status: 401, data: { detail: "reauth_required" } },
      config: {},
    };

    await expect(rejectedHandler(error)).rejects.toBe(error);

    expect(winSpy).toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  test("dispatches session-lost and shows toast on generic 401 when hadSession=true", async () => {
    const client = makeClient();
    const winSpy = jest.spyOn(window, "dispatchEvent");

    localStorage.setItem("hadSession", "true");

    installAuthInterceptors(client, { mode: "default" });
    const [, rejectedHandler] = client.interceptors.response.use.mock.calls[0];

    const error = {
      response: { status: 401, data: { detail: "Not authenticated" } },
      config: {},
    };

    await expect(rejectedHandler(error)).rejects.toBe(error);

    expect(winSpy).toHaveBeenCalled();
    expect(toast.dismiss).toHaveBeenCalledWith("session-expired");
    expect(toast.error).toHaveBeenCalled();
  });

  test("does not show session-expired toast in public mode", async () => {
    const client = makeClient();
    localStorage.setItem("hadSession", "true");

    installAuthInterceptors(client, { mode: "public" });
    const [, rejectedHandler] = client.interceptors.response.use.mock.calls[0];

    const error = {
      response: { status: 401, data: { detail: "Not authenticated" } },
      config: {},
    };

    await expect(rejectedHandler(error)).rejects.toBe(error);

    expect(toast.error).not.toHaveBeenCalled();
    expect(toast.dismiss).not.toHaveBeenCalled();
  });

  test("skips auth handling when skipAuthErrorHandling=true", async () => {
    const client = makeClient();
    localStorage.setItem("hadSession", "true");

    installAuthInterceptors(client, { mode: "default" });
    const [, rejectedHandler] = client.interceptors.response.use.mock.calls[0];

    const error = {
      response: { status: 401, data: { detail: "reauth_required" } },
      config: { skipAuthErrorHandling: true },
    };

    await expect(rejectedHandler(error)).rejects.toBe(error);

    expect(toast.error).not.toHaveBeenCalled();
    expect(toast.dismiss).not.toHaveBeenCalled();
  });
});
