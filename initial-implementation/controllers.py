import os
import random
from database import upload_to_r2, Database
from dotenv import load_dotenv

load_dotenv()

_db = Database()


class Validator:
    @staticmethod
    def validate_format(data):
        required_fields = ['title', 'author', 'email']
        for field in required_fields:
            if not data.get(field):
                return False, f"Missing required field: {field}"
        if not data.get('file_bytes'):
            return False, "Missing document upload"
        return True, "Valid"


class ReviewerManager:
    def get_available_reviewers(self):
        reviewer_list = _db.fetch_reviewers()
        filtered = self.filter_conflicts(reviewer_list)
        filtered = self.check_workload(filtered)
        return filtered

    def filter_conflicts(self, reviewer_list):
        # Baseline: no conflict data available; all reviewers pass through
        return reviewer_list

    def check_workload(self, reviewer_list):
        # Baseline: randomly select 2 reviewers as workload proxy
        return random.sample(reviewer_list, min(2, len(reviewer_list)))


class Reviewer:
    def __init__(self, reviewer_id):
        self.reviewer_id = reviewer_id

    def assign_review(self, submission_id):
        _db.save_review_assignment(submission_id, self.reviewer_id)

    def submit_score(self, submission_id, score, evaluation_manager):
        evaluation_manager.submit_score(submission_id, self.reviewer_id, score)


class NotificationService:
    def notify_acceptance(self, email, title):
        self._send(email, 'Accepted', title)

    def notify_rejection(self, email, title):
        self._send(email, 'Rejected', title)

    def notify_revision(self, email, title):
        self._send(email, 'Revision', title)

    def _send(self, email, status, title):
        import resend

        api_key = os.getenv('RESEND_API_KEY')
        if not api_key:
            print(f"[NotificationService] Notify {email}: '{status}' for '{title}'")
            return

        resend.api_key = api_key

        body = (
            f"Dear Researcher,\n\n"
            f"Your submission \"{title}\" has been reviewed.\n\n"
            f"Outcome: {status}\n\n"
            f"Thank you for your submission.\n\n"
            f"— Peer Review System"
        )

        try:
            resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": email,
                "subject": f"Research Submission {status}: {title}",
                "text": body,
            })
            print(f"[NotificationService] Email sent to {email}: {status} — {title}")
        except Exception as e:
            print(f"[NotificationService] Email error: {e}")


class EvaluationManager:
    def __init__(self):
        self.notification_service = NotificationService()

    def start_evaluation(self, submission_id):
        # Evaluation proceeds asynchronously as reviewers submit scores
        pass

    def submit_score(self, submission_id, reviewer_id, score):
        _db.save_score(submission_id, reviewer_id, score)
        self._try_finalise(submission_id)

    def _try_finalise(self, submission_id):
        scores = _db.get_scores(submission_id)
        if any(s is None for s in scores):
            return None  # Awaiting remaining reviews

        avg = self.calculate_average(scores)
        consensus = self.check_consensus(scores)
        status = self.apply_rules(avg, consensus)

        _db.update_status(submission_id, status)

        submission = _db.get_submission(submission_id)
        if submission:
            if status == 'Accepted':
                self.notification_service.notify_acceptance(
                    submission['email'], submission['title']
                )
            elif status == 'Rejected':
                self.notification_service.notify_rejection(
                    submission['email'], submission['title']
                )
            else:
                self.notification_service.notify_revision(
                    submission['email'], submission['title']
                )

        return status

    def calculate_average(self, scores):
        return sum(scores) / len(scores)

    def check_consensus(self, scores):
        return (max(scores) - min(scores)) <= 2

    def apply_rules(self, avg, consensus):
        if avg >= 7 and consensus:
            return 'Accepted'
        elif avg < 4:
            return 'Rejected'
        else:
            return 'Revision'

    def check_and_evaluate(self, submission_id):
        return self._try_finalise(submission_id)


class SubmissionController:
    def __init__(self):
        self.validator = Validator()
        self.reviewer_manager = ReviewerManager()
        self.evaluation_manager = EvaluationManager()

    def submit(self, data):
        # 1. Validate format
        is_valid, message = self.validator.validate_format(data)
        if not is_valid:
            return False, message

        # 2. Upload file and save to database
        file_name = f"{random.randint(1000, 9999)}_{data['file_name']}"
        file_path = upload_to_r2(data['file_bytes'], file_name)
        if not file_path:
            return False, "Failed to upload document"

        submission_id = _db.save_submission(
            data['title'], data['author'], data['email'], file_path
        )

        # 3. Get available reviewers and assign each one
        filtered_reviewers = self.reviewer_manager.get_available_reviewers()
        for reviewer_id in filtered_reviewers:
            reviewer = Reviewer(reviewer_id)
            reviewer.assign_review(submission_id)

        # 4. Start evaluation phase
        self.evaluation_manager.start_evaluation(submission_id)

        return True, f"Submission successful (ID: {submission_id})"
