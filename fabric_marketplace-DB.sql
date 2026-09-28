/*
SQLyog Community v13.1.1 (64 bit)
MySQL - 5.5.29 : Database - fabric_marketplace
*********************************************************************
*/

/*!40101 SET NAMES utf8 */;

/*!40101 SET SQL_MODE=''*/;

/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
CREATE DATABASE /*!32312 IF NOT EXISTS*/`fabric_marketplace` /*!40100 DEFAULT CHARACTER SET latin1 */;

USE `fabric_marketplace`;

/*Table structure for table `fabrics` */

DROP TABLE IF EXISTS `fabrics`;

CREATE TABLE `fabrics` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `type` varchar(255) NOT NULL,
  `quality_grade` enum('A','B','C') DEFAULT 'B',
  `image` varchar(255) DEFAULT NULL,
  `price` varchar(255) DEFAULT NULL,
  `seller_id` int(11) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `seller_id` (`seller_id`),
  CONSTRAINT `fabrics_ibfk_1` FOREIGN KEY (`seller_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=latin1;

/*Data for the table `fabrics` */

insert  into `fabrics`(`id`,`name`,`type`,`quality_grade`,`image`,`price`,`seller_id`,`created_at`) values 
(9,'bed shirt','silk','B','1_87.jpg','5000',3,'2025-03-02 23:42:09'),
(10,'shirt','Cotton','B','1_594.jpg','6999',3,'2025-03-02 23:44:02'),
(11,'cloth','Wool','B','1_834.jpg','3499',3,'2025-03-02 23:45:49');

/*Table structure for table `inquiries` */

DROP TABLE IF EXISTS `inquiries`;

CREATE TABLE `inquiries` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `buyer_id` int(11) NOT NULL,
  `fabric_id` int(11) NOT NULL,
  `message` text NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `buyer_id` (`buyer_id`),
  KEY `fabric_id` (`fabric_id`),
  CONSTRAINT `inquiries_ibfk_1` FOREIGN KEY (`buyer_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `inquiries_ibfk_2` FOREIGN KEY (`fabric_id`) REFERENCES `fabrics` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

/*Data for the table `inquiries` */

/*Table structure for table `transactions` */

DROP TABLE IF EXISTS `transactions`;

CREATE TABLE `transactions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `buyer_id` int(11) NOT NULL,
  `seller_id` int(11) NOT NULL,
  `fabric_id` int(11) NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `status` enum('pending','completed','cancelled') DEFAULT 'pending',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `buyer_id` (`buyer_id`),
  KEY `seller_id` (`seller_id`),
  KEY `fabric_id` (`fabric_id`),
  CONSTRAINT `transactions_ibfk_1` FOREIGN KEY (`buyer_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `transactions_ibfk_2` FOREIGN KEY (`seller_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `transactions_ibfk_3` FOREIGN KEY (`fabric_id`) REFERENCES `fabrics` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

/*Data for the table `transactions` */

/*Table structure for table `users` */

DROP TABLE IF EXISTS `users`;

CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` enum('buyer','seller','admin') NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=latin1;

/*Data for the table `users` */

insert  into `users`(`id`,`name`,`email`,`password`,`role`,`created_at`) values 
(1,'Admin','admin@gmail.com','admin','admin','2025-02-19 00:35:30'),
(2,'aravind','aravind@gmail.com','aravind','buyer','2025-02-19 00:40:29'),
(3,'venkat','venkat@gmail.com','venkat','seller','2025-02-19 01:08:48'),
(4,'ramu','ramu@gmail.com','ramu','buyer','2025-02-25 01:12:03');

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
