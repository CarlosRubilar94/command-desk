import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Density = "comfortable" | "compact";

interface DensityContextValue {
  density: Density;
  toggleDensity: () => void;
}

const DensityContext = createContext<DensityContextValue>({
  density: "comfortable",
  toggleDensity: () => {},
});

const DENSITY_KEY = "hermes-density";

function readDensity(): Density {
  try {
    const v = localStorage.getItem(DENSITY_KEY);
    return v === "compact" ? "compact" : "comfortable";
  } catch {
    return "comfortable";
  }
}

/**
 * DensityProvider — wraps the app shell and drives `data-density` on
 * `<html>`.  CSS in `devssd-tokens.css` uses that attribute to override
 * spacing tokens for compact mode.
 */
export function DensityProvider({ children }: { children: ReactNode }) {
  const [density, setDensity] = useState<Density>(readDensity);

  useEffect(() => {
    document.documentElement.setAttribute("data-density", density);
    try {
      localStorage.setItem(DENSITY_KEY, density);
    } catch {
      // localStorage unavailable
    }
  }, [density]);

  const toggleDensity = useCallback(() => {
    setDensity((d) => (d === "comfortable" ? "compact" : "comfortable"));
  }, []);

  return (
    <DensityContext.Provider value={{ density, toggleDensity }}>
      {children}
    </DensityContext.Provider>
  );
}

export function useDensity(): DensityContextValue {
  return useContext(DensityContext);
}
