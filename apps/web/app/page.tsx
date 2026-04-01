import Image from "next/image";
import Link from "next/link";
import styles from "./page.module.css";

const RESOURCES = [
  {
    title: "GitHub",
    description: "Ссылка на репозитрий проекта, с описаним архитектуры и исходным кодом",
    button: "GitHub inVision",
    link: "https://github.com/inVisionKOMO",
  },
  {
    title: "Google Disk – Презентация",
    description: "Ссылка на презентацию проекта, с показательным примером возможностей платформы",
    button: "Google Disk",
    link: "https://drive.google.com",
  },
  {
    title: "Google Disk – Документация",
    description: "Ссылка на документацию проекта, с подробным описанием решения поставленной задачи в ТЗ",
    button: "Google Disk",
    link: "https://drive.google.com/drive/folders/1Y0eQFydfT9o2MaWy7dlakuR1KfiQywtk?usp=sharing",
  },
  {
    title: "Telegram Bot",
    description: "Ссылка на bot проекта, с возможностью задать дополнительные вопросы нашей поддержки и использовать мобильную версию MiniApp",
    button: "Telegram",
    link: "https://t.me/inVisionUApp_bot",
  },
] as const;

export default function HomePage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link href="/" className={styles.logo}>
          inVision
        </Link>
        <nav className={styles.nav}>
          <Link href="/register" className={styles.navReg}>
            Регистрация
          </Link>
          <Link href="/login" className={styles.navLogin}>
            Войти
          </Link>
        </nav>
      </header>

      <div className={styles.hero}>
        <Image
          src="/assets/images/img.png"
          alt="inVision U"
          width={1920}
          height={445}
          priority
          className={styles.heroImg}
          sizes="100vw"
          unoptimized
        />
      </div>

      <main className={styles.main}>
        <p className={styles.byline}>by KOMO</p>

        <section className={styles.resources} aria-labelledby="resources-heading">
          <h2 id="resources-heading" className={styles.resourcesTitle}>
            Ресурсы KOMO
          </h2>
          <div className={styles.resourceGrid}>
            {RESOURCES.map((resource) => (
              <div key={resource.title} className={styles.resourceCard}>
                <div className={styles.resourceCardBody}>
                  <p className={styles.resourceCardTitle}>{resource.title}</p>
                  <p className={styles.resourceCardDesc}>{resource.description}</p>
                </div>
                <a
                  href={resource.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.resourceBtn}
                >
                  {resource.button}
                </a>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
