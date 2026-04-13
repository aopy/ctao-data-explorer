jest.mock("axios");
jest.mock("react-toastify", () => ({
  toast: {
    dismiss: jest.fn(),
    error: jest.fn(),
  },
}));

describe("axiosSetup interceptor", () => {
  let rejectedHandler;
  let axios;
  let toast;

  beforeEach(() => {
    jest.resetModules();
    localStorage.clear();

    Object.defineProperty(document, "cookie", {
      writable: true,
      configurable: true,
      value: "",
    });

    window.dispatchEvent = jest.fn();

    jest.isolateModules(() => {
      axios = require("axios").default || require("axios");
      toast = require("react-toastify").toast;

      axios.get.mockReset();
      axios.post.mockReset();
      axios.put.mockReset();
      axios.delete.mockReset();

      toast.dismiss.mockReset();
      toast.error.mockReset();

      axios.interceptors.response.use = jest.fn((onFulfilled, onRejected) => {
        rejectedHandler = onRejected;
      });

      require("./axiosSetup");
    });
  });

  test("dispatches reauth-required on 401 reauth_required", async () => {
    const error = {
      response: {
        status: 401,
        data: { detail: "reauth_required" },
        headers: {},
      },
      config: {},
    };

    await expect(rejectedHandler(error)).rejects.toBe(error);

    expect(toast.dismiss).toHaveBeenCalledWith("reauth-required");
    expect(toast.error).toHaveBeenCalledWith(
      "Your IAM token expired — please click Login to sign in again.",
      expect.objectContaining({
        toastId: "reauth-required",
        autoClose: false,
      })
    );
    expect(window.dispatchEvent).toHaveBeenCalledWith(expect.any(Event));
    expect(window.dispatchEvent.mock.calls[0][0].type).toBe("reauth-required");
  });

  test("dispatches session-lost on generic 401 when hadSession=true", async () => {
    localStorage.setItem("hadSession", "true");

    const error = {
      response: {
        status: 401,
        data: {},
        headers: {},
      },
      config: {},
    };

    await expect(rejectedHandler(error)).rejects.toBe(error);

    expect(toast.dismiss).toHaveBeenCalledWith("session-expired");
    expect(toast.error).toHaveBeenCalledWith(
      "Your session expired — please click the Login button to sign in again.",
      expect.objectContaining({
        toastId: "session-expired",
        autoClose: false,
      })
    );
    expect(window.dispatchEvent).toHaveBeenCalledWith(expect.any(Event));
    expect(window.dispatchEvent.mock.calls[0][0].type).toBe("session-lost");
  });

  test("skips auth handling when skipAuthErrorHandling=true", async () => {
    const error = {
      response: {
        status: 401,
        data: { detail: "reauth_required" },
        headers: {},
      },
      config: {
        skipAuthErrorHandling: true,
      },
    };

    await expect(rejectedHandler(error)).rejects.toBe(error);

    expect(toast.dismiss).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
    expect(window.dispatchEvent).not.toHaveBeenCalled();
  });
});
