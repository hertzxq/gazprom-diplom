/**
 * BlurFade — появление блока с расфокусом и сдвигом снизу (адаптация компонента
 * Magic UI blur-fade под CSS-анимацию без motion/react).
 *
 * Keyframes blurFadeIn объявлены в index.css; prefers-reduced-motion
 * отключает анимацию глобальным медиа-правилом там же.
 */
export default function BlurFade({ delay = 0, children, style, ...rest }) {
  return (
    <div
      style={{
        animation: `blurFadeIn 0.5s var(--ease-out-expo) both`,
        animationDelay: `${delay}ms`,
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}
