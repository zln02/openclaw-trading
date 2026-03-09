import PropTypes from "prop-types";
import { useEffect, useRef, useState } from "react";
import LoadingSkeleton from "./LoadingSkeleton";

export default function DeferredRender({ children, height = 280, rootMargin = "120px" }) {
  const hostRef = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!hostRef.current || visible) {
      return undefined;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin },
    );
    observer.observe(hostRef.current);
    return () => observer.disconnect();
  }, [rootMargin, visible]);

  return <div ref={hostRef}>{visible ? children : <LoadingSkeleton height={height} />}</div>;
}

DeferredRender.propTypes = {
  children: PropTypes.node,
  height: PropTypes.number,
  rootMargin: PropTypes.string,
};
