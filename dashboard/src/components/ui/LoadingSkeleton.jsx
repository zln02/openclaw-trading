import PropTypes from "prop-types";

export default function LoadingSkeleton({ height = 180, rows = 1 }) {
  if (rows > 1) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="skeleton" style={{ height: Math.round(height / rows), borderRadius: 12 }} />
        ))}
      </div>
    );
  }
  return <div className="skeleton" style={{ height, borderRadius: 20 }} />;
}

LoadingSkeleton.propTypes = {
  height: PropTypes.number,
  rows: PropTypes.number,
};
