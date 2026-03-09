import PropTypes from "prop-types";

export default function LoadingSkeleton({ height = 180 }) {
  return <div className="skeleton" style={{ height, borderRadius: 20 }} />;
}

LoadingSkeleton.propTypes = {
  height: PropTypes.number,
};
