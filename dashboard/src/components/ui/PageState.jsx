import PropTypes from "prop-types";

export function ErrorState({ message }) {
  return <div className="error-state">{message}</div>;
}

export function EmptyState({ message }) {
  return <div className="empty-state">{message}</div>;
}

ErrorState.propTypes = {
  message: PropTypes.string.isRequired,
};

EmptyState.propTypes = {
  message: PropTypes.string.isRequired,
};
