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
    def assign_reviewers(self, submission_id):
        """Fetch eligible reviewers, apply filters, and persist all assignments atomically."""
        eligible = _db.fetch_reviewers()
        eligible = self._filter_conflicts(eligible)
        selected = self._check_workload(eligible)
        _db.save_assignments(submission_id, selected)
        return selected

    def _filter_conflicts(self, reviewer_list):
        return reviewer_list

    def _check_workload(self, reviewer_list):
        return random.sample(reviewer_list, min(2, len(reviewer_list)))


class NotificationService:
    def notify(self, email, status, title):
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

    def submit_score(self, submission_id, reviewer_id, score):
        _db.save_score(submission_id, reviewer_id, score)
        self._try_finalise(submission_id)

    def _try_finalise(self, submission_id):
        scores = _db.get_scores(submission_id)
        if any(s is None for s in scores):
            return None

        status = self.evaluate(submission_id)
        _db.update_status(submission_id, status)

        submission = _db.get_submission(submission_id)
        if submission:
            self.notification_service.notify(
                submission['email'], status, submission['title']
            )

        return status

    def evaluate(self, submission_id):
        """Single decision point: computes outcome from all submitted scores."""
        scores = _db.get_scores(submission_id)
        avg = sum(scores) / len(scores)
        consensus = (max(scores) - min(scores)) <= 2
        if avg >= 7 and consensus:
            return 'Accepted'
        elif avg < 4:
            return 'Rejected'
        else:
            return 'Revision'


class SubmissionController:
    def __init__(self):
        self.validator = Validator()
        self.reviewer_manager = ReviewerManager()
        self.evaluation_manager = EvaluationManager()

    def submit(self, data):
        is_valid, message = self.validator.validate_format(data)
        if not is_valid:
            return False, message

        file_name = f"{random.randint(1000, 9999)}_{data['file_name']}"
        file_path = upload_to_r2(data['file_bytes'], file_name)
        if not file_path:
            return False, "Failed to upload document"

        submission_id = _db.save_submission(
            data['title'], data['author'], data['email'], file_path
        )

        self.reviewer_manager.assign_reviewers(submission_id)

        return True, f"Submission successful (ID: {submission_id})"
