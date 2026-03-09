import PropTypes from "prop-types";

export default function GlassCard({
  children,
  className = "",
  delay = 0,
  style,
  as: Component = "section",
}) {
  return (
    <div className="card-reveal" style={{ animationDelay: `${delay}s` }}>
      <Component className={`glass-card ${className}`.trim()} style={style}>
        {children}
      </Component>
    </div>
  );
}

GlassCard.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  delay: PropTypes.number,
  style: PropTypes.object,
  as: PropTypes.string,
};
